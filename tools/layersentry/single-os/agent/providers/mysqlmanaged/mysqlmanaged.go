package mysqlmanaged

import (
    "context"
    "errors"
    "fmt"
    "os"
    "os/user"
    "path/filepath"
    "strconv"
    "strings"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/storageplan"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/mysqlfamily"
)

const familyOwnerPath="/var/lib/layersentryd/state/mysql-family-owner"

type Provider struct{Base *mysqlfamily.Provider;Init executor.Runner}
func MySQL(base *mysqlfamily.Provider,init executor.Runner)*Provider{return &Provider{Base:base,Init:init}}
func MariaDB(base *mysqlfamily.Provider,init executor.Runner)*Provider{return &Provider{Base:base,Init:init}}
func(p *Provider)ID()string{return p.Base.ID()}
func(p *Provider)Category()model.Category{return p.Base.Category()}
func(p *Provider)Validate(_ context.Context,r model.ServiceRequest)error{if r.Category!=model.CategoryDatabase{return fmt.Errorf("%s category must be database",p.ID())};if r.Topology!="standalone"{return fmt.Errorf("%s supports standalone topology only until provider-native replication is implemented",p.ID())};if r.ReleaseLine!=p.Base.Spec.ReleaseLine{return fmt.Errorf("%s release_line must be %s",p.ID(),p.Base.Spec.ReleaseLine)};if r.Network.ListenAddress==""||r.Network.Port==0{return fmt.Errorf("%s requires an explicit guest listen IP and TCP port",p.ID())};if r.SecretRefs["admin_password"]==""{return fmt.Errorf("%s admin_password secret reference is required",p.ID())};if data,err:=storageplan.PathForPurpose(r,"database-data");err!=nil{return err}else if data!=""{if filepath.Base(data)=="data"{return errors.New("database-data mount must be a filesystem/LV root; LayerSentry creates the child data directory to avoid lost+found conflicts")}};if logs,err:=storageplan.PathForPurpose(r,"database-logs");err!=nil{return err}else if logs!=""&&filepath.Base(logs)=="logs"{return errors.New("database-logs mount must be a filesystem/LV root; LayerSentry creates the child logs directory")};if raw,err:=os.ReadFile(familyOwnerPath);err==nil&&strings.TrimSpace(string(raw))!=p.ID()+":"+r.ServiceID{return errors.New("a MySQL-family database provider already owns this guest")}else if err!=nil&&!errors.Is(err,os.ErrNotExist){return err};return nil}
func(p *Provider)ResolveVersion(ctx context.Context,r model.ServiceRequest)(string,error){return p.Base.ResolveVersion(ctx,r)}
func(p *Provider)Plan(ctx context.Context,r model.ServiceRequest,resolved string)(model.Plan,error){plan,err:=p.Base.Plan(ctx,r,resolved);if err!=nil{return plan,err};if root,_:=storageplan.PathForPurpose(r,"database-data");root!=""{plan.Steps=append([]model.PlanStep{{Name:"datadir",Action:"initialize "+p.ID()+" datadir "+filepath.Join(root,"data")+" as mysql:mysql on the attached filesystem/LV"},{Name:"selinux",Action:"persist SELinux equivalence from /var/lib/mysql to the custom database-data mount and restore contexts"}},plan.Steps...)};if root,_:=storageplan.PathForPurpose(r,"database-logs");root!=""{plan.Steps=append(plan.Steps,model.PlanStep{Name:"logs",Action:"write database error log under "+filepath.Join(root,"logs")+" with mysqld_log_t labeling"})};if p.ID()=="mysql"{plan.Steps=append(plan.Steps,model.PlanStep{Name:"local-root-auth",Action:"load MySQL auth_socket and convert root@localhost to Unix peer-credential authentication during bootstrap"})};return plan,nil}
func(p *Provider)Install(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Install(ctx,op,plan)}
func(p *Provider)Configure(ctx context.Context,op model.Operation,plan model.Plan)error{if err:=p.Base.Configure(ctx,op,plan);err!=nil{return err};raw,err:=os.ReadFile(p.configPath());if err!=nil{return err};var b strings.Builder;b.Write(raw);if len(raw)>0&&!strings.HasSuffix(string(raw),"\n"){b.WriteByte('\n')};if root,_:=storageplan.PathForPurpose(plan.Request,"database-data");root!=""{b.WriteString("datadir="+filepath.Join(root,"data")+"\n")};if root,_:=storageplan.PathForPurpose(plan.Request,"database-logs");root!=""{b.WriteString("log-error="+filepath.Join(root,"logs",p.ID()+".log")+"\n")};if p.ID()=="mysql"{b.WriteString("plugin-load-add=auth_socket.so\nauth_socket=FORCE_PLUS_PERMANENT\n")};return filesystem.AtomicWrite(p.configPath(),[]byte(b.String()),0640,"/etc/my.cnf.d")}
func(p *Provider)Initialize(ctx context.Context,op model.Operation,plan model.Plan)error{if p.Init==nil{return errors.New("database initialization helper unavailable")};if root,_:=storageplan.PathForPurpose(plan.Request,"database-data");root!=""{data:=filepath.Join(root,"data");if err:=prepareOwned(data,"mysql",0750);err!=nil{return err};if err:=p.ensureDataSELinux(ctx,root);err!=nil{return err};if _,err:=os.Stat(filepath.Join(data,"mysql"));errors.Is(err,os.ErrNotExist){switch p.ID(){case "mysql":exe:="/usr/libexec/mysqld";if _,statErr:=os.Stat(exe);statErr!=nil{exe="/usr/sbin/mysqld"};if _,err=p.Init.Run(ctx,exe,"--initialize-insecure","--user=mysql","--datadir="+data);err!=nil{return err};case "mariadb":if _,err=p.Init.Run(ctx,"/usr/bin/mariadb-install-db","--user=mysql","--datadir="+data,"--auth-root-authentication-method=socket","--skip-test-db");err!=nil{return err}}}else if err!=nil{return err}}
    if root,_:=storageplan.PathForPurpose(plan.Request,"database-logs");root!=""{logs:=filepath.Join(root,"logs");if err:=prepareOwned(logs,"mysql",0750);err!=nil{return err};if err:=p.ensureLogSELinux(ctx,root);err!=nil{return err}}
    if err:=p.Base.Initialize(ctx,op,plan);err!=nil{return err};if p.ID()=="mysql"{path:=filepath.Join("/run/layersentryd/sql-staging",plan.ServiceID,op.ID+"-bootstrap.sql");f,err:=os.OpenFile(path,os.O_WRONLY|os.O_APPEND,0);if err!=nil{return err};_,werr:=f.WriteString("ALTER USER 'root'@'localhost' IDENTIFIED WITH auth_socket;\n");cerr:=f.Close();if werr!=nil{return werr};if cerr!=nil{return cerr}};return nil}
func(p *Provider)Join(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Join(ctx,op,plan)}
func(p *Provider)Health(ctx context.Context,st model.ServiceState)(model.HealthResult,error){h,err:=p.Base.Health(ctx,st);if err==nil&&h.Checks==nil{h.Checks=map[string]string{}};if root,_:=storageplan.StatePathForPurpose(st,"database-data");root!=""{h.Checks["data_mount"]=root};return h,err}
func(p *Provider)Start(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Start(ctx,op,st)}
func(p *Provider)Stop(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Stop(ctx,op,st)}
func(p *Provider)Restart(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Restart(ctx,op,st)}
func(p *Provider)Upgrade(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Upgrade(ctx,op,plan)}
func(p *Provider)Repair(ctx context.Context,op model.Operation,plan model.Plan)error{if err:=p.Initialize(ctx,op,plan);err!=nil{return err};st:=model.ServiceState{ID:plan.ServiceID,Provider:p.ID(),Storage:plan.Request.Storage,LVM:plan.Request.LVM};return p.Start(ctx,op,st)}
func(p *Provider)Backup(ctx context.Context,op model.Operation,st model.ServiceState)(model.BackupRecord,error){return p.Base.Backup(ctx,op,st)}
func(p *Provider)Restore(ctx context.Context,op model.Operation,st model.ServiceState,b model.BackupRecord)error{return p.Base.Restore(ctx,op,st,b)}
func(p *Provider)Uninstall(ctx context.Context,op model.Operation,st model.ServiceState,destroy bool)error{return p.Base.Uninstall(ctx,op,st,destroy)}
func(p *Provider)ResidueAudit(ctx context.Context,st model.ServiceState)(map[string]string,error){return p.Base.ResidueAudit(ctx,st)}
func(p *Provider)configPath()string{return filepath.Join("/etc/my.cnf.d","99-layersentry-"+p.ID()+".cnf")}
func(p *Provider)ensureDataSELinux(ctx context.Context,root string)error{if _,err:=p.Init.Run(ctx,"/usr/sbin/semanage","fcontext","-a","-e","/var/lib/mysql",root);err!=nil{if _,err=p.Init.Run(ctx,"/usr/sbin/semanage","fcontext","-m","-e","/var/lib/mysql",root);err!=nil{return err}};_,err:=p.Init.Run(ctx,"/usr/sbin/restorecon","-RF",root);return err}
func(p *Provider)ensureLogSELinux(ctx context.Context,root string)error{pattern:=root+"(/.*)?";if _,err:=p.Init.Run(ctx,"/usr/sbin/semanage","fcontext","-a","-t","mysqld_log_t",pattern);err!=nil{if _,err=p.Init.Run(ctx,"/usr/sbin/semanage","fcontext","-m","-t","mysqld_log_t",pattern);err!=nil{return err}};_,err:=p.Init.Run(ctx,"/usr/sbin/restorecon","-RF",root);return err}
func prepareOwned(path,name string,mode os.FileMode)error{if err:=os.MkdirAll(path,mode);err!=nil{return err};if err:=os.Chmod(path,mode);err!=nil{return err};u,err:=user.Lookup(name);if err!=nil{return err};uid,err:=strconv.Atoi(u.Uid);if err!=nil{return err};gid,err:=strconv.Atoi(u.Gid);if err!=nil{return err};return os.Chown(path,uid,gid)}
