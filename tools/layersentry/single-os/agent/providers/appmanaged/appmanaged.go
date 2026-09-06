package appmanaged

import (
 "bytes"
 "context"
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "encoding/xml"
 "errors"
 "fmt"
 "io"
 "os"
 "path/filepath"
 "strings"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/provider"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/storageplan"
)

type Spec struct{Kind string}
type Provider struct{Base provider.Provider;Runner executor.Runner;Label executor.Runner;Spec Spec}
func New(base provider.Provider,runner,label executor.Runner,kind string)*Provider{return &Provider{Base:base,Runner:runner,Label:label,Spec:Spec{Kind:kind}}}
func(p *Provider)ID()string{return p.Base.ID()}
func(p *Provider)Category()model.Category{return p.Base.Category()}
func(p *Provider)Validate(ctx context.Context,r model.ServiceRequest)error{copy:=r;copy.Storage=nil;copy.LVM=nil;if err:=p.Base.Validate(ctx,copy);err!=nil{return err};root,err:=storageplan.PathForPurpose(r,"application-data");if err!=nil{return err};if root!=""&&(filepath.Base(root)=="www"||filepath.Base(root)=="webapps"){return errors.New("application-data mount must be a filesystem/LV root; LayerSentry creates the provider child directory")};return nil}
func(p *Provider)ResolveVersion(ctx context.Context,r model.ServiceRequest)(string,error){return p.Base.ResolveVersion(ctx,r)}
func(p *Provider)Plan(ctx context.Context,r model.ServiceRequest,resolved string)(model.Plan,error){plan,err:=p.Base.Plan(ctx,r,resolved);if err!=nil{return plan,err};if root,_:=storageplan.PathForPurpose(r,"application-data");root!=""{child:="www";if p.Spec.Kind=="tomcat"{child="webapps"};plan.Steps=append([]model.PlanStep{{Name:"application-data",Action:"use external application root "+filepath.Join(root,child)+" on the attached filesystem/LV"},{Name:"selinux",Action:"persist provider-appropriate SELinux content labeling for the external application root"}},plan.Steps...)};return plan,nil}
func(p *Provider)Install(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Install(ctx,op,plan)}
func(p *Provider)Configure(ctx context.Context,op model.Operation,plan model.Plan)error{if err:=p.Base.Configure(ctx,op,plan);err!=nil{return err};root,_:=storageplan.PathForPurpose(plan.Request,"application-data");if root==""{return nil};if p.Label==nil{return errors.New("application-data SELinux helper unavailable")};switch p.Spec.Kind{case "nginx","apache":return p.configureHTTP(ctx,plan,root);case "tomcat":return p.configureTomcat(ctx,plan,root);default:return errors.New("unknown application-data provider kind")}}
func(p *Provider)Initialize(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Initialize(ctx,op,plan)}
func(p *Provider)Join(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Join(ctx,op,plan)}
func(p *Provider)Health(ctx context.Context,st model.ServiceState)(model.HealthResult,error){h,err:=p.Base.Health(ctx,st);if h.Checks==nil{h.Checks=map[string]string{}};if root,_:=storageplan.StatePathForPurpose(st,"application-data");root!=""{h.Checks["application_data_mount"]=root};return h,err}
func(p *Provider)Start(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Start(ctx,op,st)}
func(p *Provider)Stop(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Stop(ctx,op,st)}
func(p *Provider)Restart(ctx context.Context,op model.Operation,st model.ServiceState)error{return p.Base.Restart(ctx,op,st)}
func(p *Provider)Upgrade(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Base.Upgrade(ctx,op,plan)}
func(p *Provider)Repair(ctx context.Context,op model.Operation,plan model.Plan)error{if err:=p.Configure(ctx,op,plan);err!=nil{return err};return p.Base.Repair(ctx,op,plan)}
func(p *Provider)Backup(ctx context.Context,op model.Operation,st model.ServiceState)(model.BackupRecord,error){return p.Base.Backup(ctx,op,st)}
func(p *Provider)Restore(ctx context.Context,op model.Operation,st model.ServiceState,b model.BackupRecord)error{return p.Base.Restore(ctx,op,st,b)}
func(p *Provider)Uninstall(ctx context.Context,op model.Operation,st model.ServiceState,destroy bool)error{if p.Spec.Kind=="tomcat"{if err:=p.restoreTomcatAppBase();err!=nil&&!errors.Is(err,os.ErrNotExist){return err}};return p.Base.Uninstall(ctx,op,st,destroy)}
func(p *Provider)ResidueAudit(ctx context.Context,st model.ServiceState)(map[string]string,error){return p.Base.ResidueAudit(ctx,st)}

func(p *Provider)configureHTTP(ctx context.Context,plan model.Plan,root string)error{app:=filepath.Join(root,"www");if err:=os.MkdirAll(app,0755);err!=nil{return err};pattern:=root+"(/.*)?";if _,err:=p.Label.Run(ctx,"/usr/sbin/semanage","fcontext","-a","-t","httpd_sys_content_t",pattern);err!=nil{if _,err=p.Label.Run(ctx,"/usr/sbin/semanage","fcontext","-m","-t","httpd_sys_content_t",pattern);err!=nil{return err}};if _,err:=p.Label.Run(ctx,"/usr/sbin/restorecon","-RF",root);err!=nil{return err};switch p.Spec.Kind{case "nginx":if err:=filesystem.AtomicWrite(filepath.Join(app,"index.html"),[]byte("LayerSentry managed Nginx application service\n"),0644,app);err!=nil{return err};sum:=sha256.Sum256([]byte(plan.ServiceID));conf:=filepath.Join("/etc/nginx/conf.d","layersentry-"+hex.EncodeToString(sum[:6])+".conf");raw,err:=os.ReadFile(conf);if err!=nil{return err};old:=filepath.Join("/var/lib/layersentryd/apps",plan.ServiceID,"www");text:=strings.ReplaceAll(string(raw),"root "+old+";","root "+app+";");if text==string(raw){return errors.New("Nginx managed root directive was not found for external application-data rewrite")};if err=filesystem.AtomicWrite(conf,[]byte(text),0644,"/etc/nginx/conf.d");err!=nil{return err};_ = os.RemoveAll(filepath.Join("/var/lib/layersentryd/apps",plan.ServiceID));_,err=p.Runner.Run(ctx,"/usr/sbin/nginx","-t");return err;case "apache":if err:=filesystem.AtomicWrite(filepath.Join(app,"index.html"),[]byte("LayerSentry managed Apache HTTP service\n"),0644,app);err!=nil{return err};if err:=filesystem.AtomicWrite(filepath.Join(app,".layersentry-health"),[]byte("layersentry-ok\n"),0644,app);err!=nil{return err};sum:=sha256.Sum256([]byte(plan.ServiceID));conf:=filepath.Join("/etc/httpd/conf.d","layersentry-"+hex.EncodeToString(sum[:6])+".conf");raw,err:=os.ReadFile(conf);if err!=nil{return err};old:=filepath.Join("/var/www/html","layersentry-"+hex.EncodeToString(sum[:6]));text:=strings.ReplaceAll(string(raw),old,app);if text==string(raw){return errors.New("Apache managed DocumentRoot was not found for external application-data rewrite")};if err=filesystem.AtomicWrite(conf,[]byte(text),0644,"/etc/httpd/conf.d");err!=nil{return err};_ = os.RemoveAll(old);_,err=p.Runner.Run(ctx,"/usr/sbin/httpd","-t");return err};return nil}

type hostBackup struct{AppBase string `json:"app_base"`;Had bool `json:"had"`}
const tomcatXML="/etc/tomcat/server.xml"
const tomcatBackup="/var/lib/layersentryd/state/tomcat-appbase.json"
func(p *Provider)configureTomcat(ctx context.Context,plan model.Plan,root string)error{webapps:=filepath.Join(root,"webapps");if err:=os.MkdirAll(webapps,0755);err!=nil{return err};if _,err:=p.Label.Run(ctx,"/usr/sbin/semanage","fcontext","-a","-e","/var/lib/tomcat",root);err!=nil{if _,err=p.Label.Run(ctx,"/usr/sbin/semanage","fcontext","-m","-e","/var/lib/tomcat",root);err!=nil{return err}};if _,err:=p.Label.Run(ctx,"/usr/sbin/restorecon","-RF",root);err!=nil{return err};return rewriteTomcatHost(webapps,false)}
func(p *Provider)restoreTomcatAppBase()error{return rewriteTomcatHost("",true)}
func rewriteTomcatHost(appBase string,restore bool)error{raw,err:=os.ReadFile(tomcatXML);if err!=nil{return err};var saved hostBackup;if restore{b,err:=os.ReadFile(tomcatBackup);if err!=nil{return err};if err=json.Unmarshal(b,&saved);err!=nil{return err}}
 dec:=xml.NewDecoder(bytes.NewReader(raw));var out bytes.Buffer;enc:=xml.NewEncoder(&out);matches:=0
 for{tok,err:=dec.Token();if errors.Is(err,io.EOF){break};if err!=nil{return err};if start,ok:=tok.(xml.StartElement);ok&&start.Name.Local=="Host"{matches++;if matches>1{return errors.New("multiple Tomcat Host elements found; refusing ambiguous appBase rewrite")};if restore{start=restoreHost(start,saved)}else{var backup hostBackup;start,backup=setHost(start,appBase);if _,e:=os.Lstat(tomcatBackup);errors.Is(e,os.ErrNotExist){b,_:=json.MarshalIndent(backup,"","  ");if e=filesystem.AtomicWrite(tomcatBackup,append(b,'\n'),0600,"/var/lib/layersentryd/state");e!=nil{return e}}else if e!=nil{return e}};tok=start};if err=enc.EncodeToken(tok);err!=nil{return err}}
 if matches!=1{return errors.New("exactly one Tomcat Host is required")};if err=enc.Flush();err!=nil{return err};if err=filesystem.AtomicWrite(tomcatXML,out.Bytes(),0644,"/etc/tomcat");err!=nil{return err};if restore{_ = os.Remove(tomcatBackup)};return nil}
func setHost(s xml.StartElement,value string)(xml.StartElement,hostBackup){b:=hostBackup{};found:=false;for i,a:=range s.Attr{if a.Name.Local=="appBase"{b.AppBase=a.Value;b.Had=true;s.Attr[i].Value=value;found=true}};if !found{s.Attr=append(s.Attr,xml.Attr{Name:xml.Name{Local:"appBase"},Value:value})};return s,b}
func restoreHost(s xml.StartElement,b hostBackup)xml.StartElement{out:=make([]xml.Attr,0,len(s.Attr));found:=false;for _,a:=range s.Attr{if a.Name.Local=="appBase"{if b.Had{a.Value=b.AppBase;out=append(out,a);found=true};continue};out=append(out,a)};if b.Had&&!found{out=append(out,xml.Attr{Name:xml.Name{Local:"appBase"},Value:b.AppBase})};s.Attr=out;return s}
