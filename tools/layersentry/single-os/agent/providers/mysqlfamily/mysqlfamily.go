package mysqlfamily

import (
    "bytes"
    "context"
    "crypto/rand"
    "crypto/rsa"
    "crypto/sha256"
    "crypto/x509"
    "crypto/x509/pkix"
    "encoding/hex"
    "encoding/pem"
    "errors"
    "fmt"
    "io"
    "math/big"
    "net"
    "os"
    "os/user"
    "path/filepath"
    "strconv"
    "strings"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/backupcrypto"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/packageutil"
)

const (
    repoID          = "appstream"
    familyOwnerPath = "/var/lib/layersentryd/state/mysql-family-owner"
)

type SecretGetter interface { Get(string) ([]byte, error) }

type Spec struct {
    ID            string
    Package       string
    Conflict      string
    ServiceUnit   string
    ClientPath    string
    DumpPath      string
    ReleaseLine   string
    VersionPrefix string
}

type Provider struct {
    Runner  executor.Runner
    DNF     packageutil.DNF
    Secrets SecretGetter
    Backups *backupcrypto.Keyring
    Spec    Spec
}

func New(r executor.Runner, secrets SecretGetter, backups *backupcrypto.Keyring, spec Spec) *Provider {
    return &Provider{Runner:r, DNF:packageutil.DNF{Runner:r}, Secrets:secrets, Backups:backups, Spec:spec}
}
func MariaDB(r executor.Runner,secrets SecretGetter,backups *backupcrypto.Keyring)*Provider{return New(r,secrets,backups,Spec{ID:"mariadb",Package:"mariadb-server",Conflict:"mysql-server",ServiceUnit:"mariadb.service",ClientPath:"/usr/bin/mariadb",DumpPath:"/usr/bin/mariadb-dump",ReleaseLine:"10.5",VersionPrefix:"10.5"})}
func MySQL(r executor.Runner,secrets SecretGetter,backups *backupcrypto.Keyring)*Provider{return New(r,secrets,backups,Spec{ID:"mysql",Package:"mysql-server",Conflict:"mariadb-server",ServiceUnit:"mysqld.service",ClientPath:"/usr/bin/mysql",DumpPath:"/usr/bin/mysqldump",ReleaseLine:"8.0",VersionPrefix:"8.0"})}

func(p *Provider)ID()string{return p.Spec.ID}
func(p *Provider)Category()model.Category{return model.CategoryDatabase}

func(p *Provider)Validate(_ context.Context,r model.ServiceRequest)error{
    if r.Category!=model.CategoryDatabase{return fmt.Errorf("%s category must be database",p.Spec.ID)}
    if r.Topology!="standalone"{return fmt.Errorf("%s supports standalone topology only until provider-native replication is implemented",p.Spec.ID)}
    if r.ReleaseLine!=p.Spec.ReleaseLine{return fmt.Errorf("%s release_line must be %s on the qualified Rocky AppStream path",p.Spec.ID,p.Spec.ReleaseLine)}
    if net.ParseIP(r.Network.ListenAddress)==nil||r.Network.Port==0{return fmt.Errorf("%s requires an explicit guest listen IP and TCP port",p.Spec.ID)}
    if r.SecretRefs["admin_password"]==""{return fmt.Errorf("%s admin_password secret reference is required",p.Spec.ID)}
    if len(r.Storage)!=0{return fmt.Errorf("%s attached-data relocation is not qualified yet; omit storage assignments",p.Spec.ID)}
    if err:=p.ensureOwnerAvailable(r.ServiceID);err!=nil{return err}
    return nil
}

func(p *Provider)ResolveVersion(ctx context.Context,_ model.ServiceRequest)(string,error){if err:=p.DNF.ValidateRepositories(ctx,repoID);err!=nil{return "",err};v,err:=p.DNF.ResolveLatestFromRepos(ctx,p.Spec.Package,[]string{repoID});if err!=nil{return "",err};if !versionMatches(p.Spec.Package,v,p.Spec.VersionPrefix){return "",fmt.Errorf("%s AppStream resolved %q outside qualified %s release line",p.Spec.ID,v,p.Spec.VersionPrefix)};return v,nil}
func(p *Provider)Plan(ctx context.Context,r model.ServiceRequest,resolved string)(model.Plan,error){repoDigest,err:=p.DNF.RepositoryDigest(ctx,repoID);if err!=nil{return model.Plan{},err};steps:=[]model.PlanStep{{Name:"repository",Action:"use Rocky AppStream with GPG/TLS verification"},{Name:"packages",Action:"install exact "+p.Spec.Package+" package "+resolved},{Name:"tls",Action:"generate service-owned TLS key/certificate and require encrypted remote transport"},{Name:"configure",Action:fmt.Sprintf("bind %s to %s:%d with local infile and symbolic links disabled",p.Spec.ID,r.Network.ListenAddress,r.Network.Port)},{Name:"firewall",Action:"allow only requested CIDRs before first network service start"},{Name:"bootstrap",Action:"create/update layersentry_admin through local root socket using an ephemeral /run SQL script; never place the password in argv"},{Name:"health",Action:"validate systemd state and SELECT VERSION() over the local socket"}};if r.Backup.Enabled{steps=append(steps,model.PlanStep{Name:"backup-policy",Action:"logical all-database backups are staged in /run, encrypted with age X25519 before persistence, then cataloged with ciphertext/plaintext integrity"})};sum:=sha256.Sum256([]byte(fmt.Sprintf("%s|%s|%s|%s|%s|%v",r.ServiceID,p.Spec.ID,resolved,repoID,repoDigest,steps)));return model.Plan{ID:r.OperationID,ServiceID:r.ServiceID,Provider:p.ID(),ResolvedVersion:resolved,RepositoryID:repoID,RepositoryDigest:repoDigest,Digest:hex.EncodeToString(sum[:]),CreatedAt:time.Now().UTC(),Request:r,Steps:steps},nil}
func(p *Provider)Install(ctx context.Context,_ model.Operation,plan model.Plan)error{if err:=p.ensureOwnerAvailable(plan.ServiceID);err!=nil{return err};if r,_:=p.Runner.Run(ctx,"/usr/bin/rpm","-q",p.Spec.Conflict);r.ExitCode==0{return fmt.Errorf("%s conflicts with installed %s",p.Spec.ID,p.Spec.Conflict)};if plan.RepositoryID!=repoID||plan.RepositoryDigest==""{return errors.New("mysql-family plan repository provenance missing")};d,err:=p.DNF.RepositoryDigest(ctx,repoID);if err!=nil{return err};if d!=plan.RepositoryDigest{return errors.New("mysql-family repository configuration drifted after plan confirmation")};return p.DNF.InstallExactFromRepos(ctx,[]string{repoID},plan.ResolvedVersion)}

func(p *Provider)Configure(ctx context.Context,_ model.Operation,plan model.Plan)error{if err:=p.claimOwner(plan.ServiceID);err!=nil{return err};cert,key,err:=p.ensureTLS(plan.ServiceID,plan.Request.Network.ListenAddress);if err!=nil{return err};conf:=fmt.Sprintf("[mysqld]\nbind-address=%s\nport=%d\nskip-name-resolve=1\nlocal-infile=0\nsymbolic-links=0\nrequire_secure_transport=ON\nssl-ca=%s\nssl-cert=%s\nssl-key=%s\n",plan.Request.Network.ListenAddress,plan.Request.Network.Port,cert,cert,key);if err=filesystem.AtomicWrite(p.configPath(),[]byte(conf),0640,"/etc/my.cnf.d");err!=nil{return err};_,_ = p.Runner.Run(ctx,"/usr/sbin/restorecon","-F",p.configPath());return nil}
func(p *Provider)Initialize(_ context.Context,op model.Operation,plan model.Plan)error{if p.Secrets==nil{return errors.New("secret store unavailable")};secret,err:=p.Secrets.Get(plan.Request.SecretRefs["admin_password"]);if err!=nil{return err};defer zero(secret);if len(secret)<12||len(secret)>1024{return errors.New("database admin password length outside 12..1024 bytes")};stage,err:=p.stageDir(plan.ServiceID);if err!=nil{return err};hexpw:=hex.EncodeToString(secret);sql:=fmt.Sprintf("SET @ls_pw = CONVERT(0x%s USING utf8mb4);\nSET @ls_q = CONCAT(\"CREATE USER IF NOT EXISTS 'layersentry_admin'@'%%' IDENTIFIED BY \" , QUOTE(@ls_pw));\nPREPARE ls_s FROM @ls_q; EXECUTE ls_s; DEALLOCATE PREPARE ls_s;\nSET @ls_q = CONCAT(\"ALTER USER 'layersentry_admin'@'%%' IDENTIFIED BY \" , QUOTE(@ls_pw), \" REQUIRE SSL\");\nPREPARE ls_s FROM @ls_q; EXECUTE ls_s; DEALLOCATE PREPARE ls_s;\nGRANT ALL PRIVILEGES ON *.* TO 'layersentry_admin'@'%%' WITH GRANT OPTION;\nFLUSH PRIVILEGES;\n",hexpw);path:=filepath.Join(stage,op.ID+"-bootstrap.sql");return filesystem.AtomicWrite(path,[]byte(sql),0600,stage)}
func(p *Provider)Join(context.Context,model.Operation,model.Plan)error{return errors.New("mysql-family cluster join is not implemented")}

func(p *Provider)Start(ctx context.Context,op model.Operation,st model.ServiceState)error{if _,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","enable","--now",p.Spec.ServiceUnit);err!=nil{return err};path:=filepath.Join("/run/layersentryd/sql-staging",st.ID,op.ID+"-bootstrap.sql");if _,err:=os.Lstat(path);errors.Is(err,os.ErrNotExist){return nil}else if err!=nil{return err};defer os.Remove(path);_,err:=p.Runner.Run(ctx,p.Spec.ClientPath,"--protocol=socket","--user=root","--execute=source "+path);return err}
func(p *Provider)Stop(ctx context.Context,_ model.Operation,_ model.ServiceState)error{_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","stop",p.Spec.ServiceUnit);return err}
func(p *Provider)Restart(ctx context.Context,_ model.Operation,_ model.ServiceState)error{_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","restart",p.Spec.ServiceUnit);return err}
func(p *Provider)Health(ctx context.Context,_ model.ServiceState)(model.HealthResult,error){checks:=map[string]string{};r,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","is-active",p.Spec.ServiceUnit);if err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:p.Spec.ServiceUnit+" is not active"},nil};checks["systemd"]=strings.TrimSpace(r.Stdout);q,err:=p.Runner.Run(ctx,p.Spec.ClientPath,"--protocol=socket","--user=root","--batch","--skip-column-names","--execute=SELECT VERSION()");if err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:"local SQL health query failed"},nil};version:=strings.TrimSpace(q.Stdout);if version==""{return model.HealthResult{Healthy:false,Checks:checks,Error:"database version response is empty"},nil};checks["sql"]="ok";checks["tls"]="required-for-network";return model.HealthResult{Healthy:true,Version:version,Checks:checks},nil}
func(p *Provider)Upgrade(ctx context.Context,op model.Operation,plan model.Plan)error{if err:=p.Install(ctx,op,plan);err!=nil{return err};if _,_,err:=p.ensureTLS(plan.ServiceID,plan.Request.Network.ListenAddress);err!=nil{return err};_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","restart",p.Spec.ServiceUnit);return err}
func(p *Provider)Repair(ctx context.Context,op model.Operation,plan model.Plan)error{if err:=p.Initialize(ctx,op,plan);err!=nil{return err};st:=model.ServiceState{ID:plan.ServiceID,Provider:p.ID()};return p.Start(ctx,op,st)}

func(p *Provider)Backup(ctx context.Context,op model.Operation,st model.ServiceState)(model.BackupRecord,error){if p.Backups==nil{return model.BackupRecord{},errors.New("backup encryption keyring unavailable")};stage,err:=p.stageDir(st.ID);if err!=nil{return model.BackupRecord{},err};plain:=filepath.Join(stage,op.ID+"-db-dump.sql");defer os.Remove(plain);args:=[]string{"--protocol=socket","--user=root","--all-databases","--single-transaction","--routines","--events","--hex-blob","--result-file="+plain};if _,err=p.Runner.Run(ctx,p.Spec.DumpPath,args...);err!=nil{return model.BackupRecord{},err};_ = os.Chmod(plain,0600);plainSHA,plainSize,err:=inspectSQLDump(plain);if err!=nil{return model.BackupRecord{},err};root:=filepath.Join("/var/lib/layersentryd/backups",st.ID);if err=os.MkdirAll(root,0700);err!=nil{return model.BackupRecord{},err};cipher:=filepath.Join(root,op.ID+"-"+p.Spec.ID+".sql.age");d,err:=p.Backups.EncryptFile(plain,stage,cipher,root);if err!=nil{return model.BackupRecord{},err};if err=os.Remove(plain);err!=nil{_ = os.Remove(cipher);return model.BackupRecord{},err};return model.BackupRecord{ID:op.ID,ServiceID:st.ID,Provider:p.ID(),Path:cipher,SHA256:d.SHA256,SizeBytes:d.SizeBytes,PlaintextSHA256:plainSHA,PlaintextSizeBytes:plainSize,Encryption:"age-x25519-v1",KeyID:p.Backups.ActiveKeyID(),Verified:true,CreatedAt:time.Now().UTC()},nil}
func(p *Provider)Restore(ctx context.Context,_ model.Operation,st model.ServiceState,b model.BackupRecord)error{if p.Backups==nil{return errors.New("backup encryption keyring unavailable")};if !b.Verified||b.Provider!=p.ID()||b.ServiceID!=st.ID||b.Encryption!="age-x25519-v1"{return errors.New("backup identity/encryption verification failed")};root:=filepath.Join("/var/lib/layersentryd/backups",st.ID);clean:=filepath.Clean(b.Path);rel,err:=filepath.Rel(root,clean);if err!=nil||rel==".."||strings.HasPrefix(rel,".."+string(filepath.Separator)){return errors.New("backup path outside service backup root")};if err=backupcrypto.VerifyCiphertext(clean,root,b.SHA256,b.SizeBytes);err!=nil{return err};stage,err:=p.stageDir(st.ID);if err!=nil{return err};plain:=filepath.Join(stage,b.ID+"-db-restore.sql");defer os.Remove(plain);if err=p.Backups.DecryptFile(clean,root,plain,stage);err!=nil{return err};sha,size,err:=inspectSQLDump(plain);if err!=nil{return err};if sha!=b.PlaintextSHA256||size!=b.PlaintextSizeBytes{return errors.New("decrypted database backup integrity mismatch")};_,err=p.Runner.Run(ctx,p.Spec.ClientPath,"--protocol=socket","--user=root","--execute=source "+plain);return err}
func(p *Provider)Uninstall(ctx context.Context,_ model.Operation,st model.ServiceState,destroyData bool)error{if destroyData{return errors.New("database data destruction requires a separate explicit authorization path")};if _,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","disable","--now",p.Spec.ServiceUnit);err!=nil{return err};if err:=os.Remove(p.configPath());err!=nil&&!errors.Is(err,os.ErrNotExist){return err};_ = os.RemoveAll(p.tlsDir(st.ID));if err:=os.Remove(familyOwnerPath);err!=nil&&!errors.Is(err,os.ErrNotExist){return err};return p.DNF.Remove(ctx,p.Spec.Package)}
func(p *Provider)ResidueAudit(ctx context.Context,st model.ServiceState)(map[string]string,error){out:=map[string]string{"customer_data":"preserved"};r,_:=p.Runner.Run(ctx,"/usr/bin/rpm","-q",p.Spec.Package);if r.ExitCode==0{out["rpm"]="present"}else{out["rpm"]="absent"};r,_=p.Runner.Run(ctx,"/usr/bin/systemctl","is-active",p.Spec.ServiceUnit);if r.ExitCode==0{out["service"]="active"}else{out["service"]="inactive"};if _,err:=os.Lstat(p.configPath());err==nil{out["managed_config"]="present"}else{out["managed_config"]="absent"};if _,err:=os.Lstat(p.tlsDir(st.ID));err==nil{out["managed_tls"]="present"}else{out["managed_tls"]="absent"};return out,nil}

func(p *Provider)configPath()string{return filepath.Join("/etc/my.cnf.d","99-layersentry-"+p.Spec.ID+".cnf")}
func(p *Provider)tlsDir(serviceID string)string{return filepath.Join("/var/lib/mysql","layersentry-"+serviceID)}
func(p *Provider)stageDir(serviceID string)(string,error){root:=filepath.Join("/run/layersentryd/sql-staging",serviceID);if err:=os.MkdirAll(root,0700);err!=nil{return "",err};fi,err:=os.Lstat(root);if err!=nil{return "",err};if !fi.IsDir()||fi.Mode()&os.ModeSymlink!=0||fi.Mode().Perm()&0002!=0{return "",errors.New("unsafe database SQL staging directory")};return root,nil}
func(p *Provider)ensureOwnerAvailable(serviceID string)error{raw,err:=os.ReadFile(familyOwnerPath);if errors.Is(err,os.ErrNotExist){return nil};if err!=nil{return err};want:=p.Spec.ID+":"+serviceID;if strings.TrimSpace(string(raw))!=want{return errors.New("a MySQL-family database provider already owns this guest")};return nil}
func(p *Provider)claimOwner(serviceID string)error{if err:=p.ensureOwnerAvailable(serviceID);err!=nil{return err};return filesystem.AtomicWrite(familyOwnerPath,[]byte(p.Spec.ID+":"+serviceID+"\n"),0600,"/var/lib/layersentryd/state")}

func(p *Provider)ensureTLS(serviceID,ip string)(string,string,error){dir:=p.tlsDir(serviceID);if err:=os.MkdirAll(dir,0700);err!=nil{return "","",err};certPath:=filepath.Join(dir,"server.crt");keyPath:=filepath.Join(dir,"server.key");if certRaw,err:=os.ReadFile(certPath);err==nil{block,_:=pem.Decode(certRaw);if block!=nil{if cert,err:=x509.ParseCertificate(block.Bytes);err==nil&&time.Until(cert.NotAfter)>30*24*time.Hour{if _,err=os.Lstat(keyPath);err==nil{return certPath,keyPath,nil}}}};key,err:=rsa.GenerateKey(rand.Reader,3072);if err!=nil{return "","",err};serialLimit:=new(big.Int).Lsh(big.NewInt(1),128);serial,err:=rand.Int(rand.Reader,serialLimit);if err!=nil{return "","",err};now:=time.Now().UTC();tmpl:=x509.Certificate{SerialNumber:serial,Subject:pkix.Name{CommonName:"LayerSentry "+p.Spec.ID},NotBefore:now.Add(-5*time.Minute),NotAfter:now.Add(397*24*time.Hour),KeyUsage:x509.KeyUsageDigitalSignature|x509.KeyUsageKeyEncipherment,ExtKeyUsage:[]x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},BasicConstraintsValid:true,IPAddresses:[]net.IP{net.ParseIP(ip)}};der,err:=x509.CreateCertificate(rand.Reader,&tmpl,&tmpl,&key.PublicKey,key);if err!=nil{return "","",err};certPEM:=pem.EncodeToMemory(&pem.Block{Type:"CERTIFICATE",Bytes:der});keyPEM:=pem.EncodeToMemory(&pem.Block{Type:"RSA PRIVATE KEY",Bytes:x509.MarshalPKCS1PrivateKey(key)});if err=filesystem.AtomicWrite(certPath,certPEM,0644,dir);err!=nil{return "","",err};if err=filesystem.AtomicWrite(keyPath,keyPEM,0600,dir);err!=nil{return "","",err};if err=chownTree(dir,"mysql");err!=nil{return "","",err};_,_ = p.Runner.Run(context.Background(),"/usr/sbin/restorecon","-RF",dir);return certPath,keyPath,nil}
func chownTree(root,name string)error{u,err:=user.Lookup(name);if err!=nil{return err};uid,err:=strconv.Atoi(u.Uid);if err!=nil{return err};gid,err:=strconv.Atoi(u.Gid);if err!=nil{return err};return filepath.Walk(root,func(path string,info os.FileInfo,err error)error{if err!=nil{return err};return os.Chown(path,uid,gid)})}
func inspectSQLDump(path string)(string,int64,error){fi,err:=os.Lstat(path);if err!=nil{return "",0,err};if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular()||fi.Size()<128{return "",0,errors.New("database logical backup is empty or unsafe")};f,err:=os.Open(path);if err!=nil{return "",0,err};defer f.Close();head:=make([]byte,64<<10);n,_:=f.Read(head);if _,err=f.Seek(0,0);err!=nil{return "",0,err};lower:=bytes.ToLower(head[:n]);if !bytes.Contains(lower,[]byte("dump"))||(!bytes.Contains(lower,[]byte("mysql"))&&!bytes.Contains(lower,[]byte("mariadb"))){return "",0,errors.New("database logical backup structure verification failed")};h:=sha256.New();if _,err=io.Copy(h,f);err!=nil{return "",0,err};return hex.EncodeToString(h.Sum(nil)),fi.Size(),nil}
func versionMatches(pkg,nevra,prefix string)bool{rest:=strings.TrimPrefix(nevra,pkg+"-");if rest==nevra{return false};if i:=strings.IndexByte(rest,':');i>=0{rest=rest[i+1:]};return rest==prefix||strings.HasPrefix(rest,prefix+".")}
func zero(b []byte){for i:=range b{b[i]=0}}
