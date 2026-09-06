package tomcat

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
    "net"
    "net/http"
    "os"
    "strings"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/packageutil"
)

const (
    repoID      = "appstream"
    packageName = "tomcat"
    serviceUnit = "tomcat.service"
    serverXML   = "/etc/tomcat/server.xml"
    ownerPath   = "/var/lib/layersentryd/state/tomcat-owner"
    backupPath  = "/var/lib/layersentryd/state/tomcat-original-connector.json"
)

type connectorBackup struct {
    Port       string `json:"port"`
    Address    string `json:"address,omitempty"`
    HadAddress bool   `json:"had_address"`
}

type Provider struct {
    Runner executor.Runner
    DNF    packageutil.DNF
}

func New(r executor.Runner) *Provider { return &Provider{Runner: r, DNF: packageutil.DNF{Runner: r}} }
func (p *Provider) ID() string { return "tomcat" }
func (p *Provider) Category() model.Category { return model.CategoryApplication }

func (p *Provider) Validate(_ context.Context, r model.ServiceRequest) error {
    if r.Category != model.CategoryApplication { return errors.New("tomcat category must be application") }
    if r.Topology != "standalone" { return errors.New("tomcat supports standalone topology only") }
    if r.ReleaseLine != "rocky9" && r.ReleaseLine != "stable" { return errors.New("tomcat release_line must be rocky9 or stable") }
    if net.ParseIP(r.Network.ListenAddress) == nil || r.Network.Port == 0 { return errors.New("tomcat requires an explicit guest listen IP and TCP port") }
    if r.Backup.Enabled || r.Backup.Schedule != "" || r.Backup.Retention != 0 { return errors.New("tomcat does not own deployed-application backup; backup policy must be disabled") }
    if len(r.Storage) != 0 { return errors.New("tomcat provider does not consume attached storage yet; omit storage assignments") }
    if owner, err := os.ReadFile(ownerPath); err == nil && strings.TrimSpace(string(owner)) != r.ServiceID {
        return errors.New("tomcat is single-instance on a guest and is already owned by another service")
    } else if err != nil && !errors.Is(err, os.ErrNotExist) { return err }
    return nil
}

func (p *Provider) ResolveVersion(ctx context.Context, _ model.ServiceRequest) (string, error) {
    if err := p.DNF.ValidateRepositories(ctx, repoID); err != nil { return "", err }
    return p.DNF.ResolveLatestFromRepos(ctx, packageName, []string{repoID})
}

func (p *Provider) Plan(ctx context.Context, r model.ServiceRequest, resolved string) (model.Plan, error) {
    repoDigest, err := p.DNF.RepositoryDigest(ctx, repoID); if err != nil { return model.Plan{}, err }
    steps := []model.PlanStep{
        {Name:"repository", Action:"use Rocky AppStream with GPG/TLS verification"},
        {Name:"packages", Action:"install exact Rocky-supported Tomcat package "+resolved},
        {Name:"configure", Action:fmt.Sprintf("rewrite exactly one HTTP/1.1 Connector to %s:%d while retaining original connector attributes", r.Network.ListenAddress, r.Network.Port)},
        {Name:"firewall", Action:"allow only requested CIDRs to the requested TCP port"},
        {Name:"service", Action:"enable and start tomcat.service"},
        {Name:"health", Action:"validate systemd state, local HTTP response and installed package identity"},
    }
    sum := sha256.Sum256([]byte(fmt.Sprintf("%s|%s|%s|%s|%v", r.ServiceID, resolved, repoID, repoDigest, steps)))
    return model.Plan{ID:r.OperationID, ServiceID:r.ServiceID, Provider:p.ID(), ResolvedVersion:resolved, RepositoryID:repoID, RepositoryDigest:repoDigest, Digest:hex.EncodeToString(sum[:]), CreatedAt:time.Now().UTC(), Request:r, Steps:steps}, nil
}

func (p *Provider) Install(ctx context.Context, _ model.Operation, plan model.Plan) error {
    if err := ensureOwnerAvailable(plan.ServiceID); err != nil { return err }
    if plan.RepositoryID != repoID || plan.RepositoryDigest == "" { return errors.New("tomcat plan repository provenance missing") }
    current, err := p.DNF.RepositoryDigest(ctx, repoID); if err != nil { return err }
    if current != plan.RepositoryDigest { return errors.New("tomcat repository configuration drifted after plan confirmation") }
    return p.DNF.InstallExactFromRepos(ctx, []string{repoID}, plan.ResolvedVersion)
}

func (p *Provider) Configure(_ context.Context, _ model.Operation, plan model.Plan) error {
    if err := claimOwner(plan.ServiceID); err != nil { return err }
    return rewriteConnector(plan.Request.Network.ListenAddress, plan.Request.Network.Port, false)
}
func (p *Provider) Initialize(context.Context, model.Operation, model.Plan) error { return nil }
func (p *Provider) Join(context.Context, model.Operation, model.Plan) error { return errors.New("tomcat cluster join is not supported") }
func (p *Provider) Start(ctx context.Context, _ model.Operation, _ model.ServiceState) error { _,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","enable","--now",serviceUnit);return err }
func (p *Provider) Stop(ctx context.Context, _ model.Operation, _ model.ServiceState) error { _,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","stop",serviceUnit);return err }
func (p *Provider) Restart(ctx context.Context, _ model.Operation, _ model.ServiceState) error { _,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","restart",serviceUnit);return err }

func (p *Provider) Health(ctx context.Context, st model.ServiceState) (model.HealthResult, error) {
    checks:=map[string]string{}
    r,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","is-active",serviceUnit);if err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:"tomcat.service is not active"},nil};checks["systemd"]=strings.TrimSpace(r.Stdout)
    tr:=&http.Transport{Proxy:nil,DisableKeepAlives:true,DialContext:(&net.Dialer{Timeout:2*time.Second}).DialContext}
    client:=&http.Client{Timeout:3*time.Second,Transport:tr,CheckRedirect:func(_ *http.Request,_ []*http.Request)error{return errors.New("redirect rejected")}}
    resp,err:=client.Get(fmt.Sprintf("http://%s:%d/",st.Network.ListenAddress,st.Network.Port));if err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:"local Tomcat HTTP health request failed"},nil};defer resp.Body.Close();_,_ = io.Copy(io.Discard,io.LimitReader(resp.Body,4<<10));if resp.StatusCode<100||resp.StatusCode>=500{return model.HealthResult{Healthy:false,Checks:checks,Error:"Tomcat returned unhealthy HTTP status"},nil};checks["http"]=fmt.Sprintf("%d",resp.StatusCode)
    pkg,err:=p.Runner.Run(ctx,"/usr/bin/rpm","-q",packageName);if err!=nil{return model.HealthResult{Healthy:false,Checks:checks,Error:"tomcat package identity unavailable"},nil};version:=strings.TrimSpace(pkg.Stdout);checks["version"]=version
    return model.HealthResult{Healthy:true,Version:version,Checks:checks},nil
}
func (p *Provider) Upgrade(ctx context.Context, op model.Operation, plan model.Plan) error { if err:=p.Install(ctx,op,plan);err!=nil{return err};_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","restart",serviceUnit);return err }
func (p *Provider) Repair(ctx context.Context, _ model.Operation, _ model.Plan) error { if err:=validateServerXML();err!=nil{return err};_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","restart",serviceUnit);return err }
func (p *Provider) Backup(context.Context, model.Operation, model.ServiceState)(model.BackupRecord,error){return model.BackupRecord{},errors.New("tomcat does not own deployed-application backup")}
func (p *Provider) Restore(context.Context, model.Operation, model.ServiceState, model.BackupRecord)error{return errors.New("tomcat does not own deployed-application restore")}
func (p *Provider) Uninstall(ctx context.Context,_ model.Operation,_ model.ServiceState,destroyData bool)error{if destroyData{return errors.New("tomcat uninstall never destroys deployed application data")};if _,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","disable","--now",serviceUnit);err!=nil{return err};if err:=rewriteConnector("",0,true);err!=nil{return err};if err:=os.Remove(ownerPath);err!=nil&&!errors.Is(err,os.ErrNotExist){return err};return p.DNF.Remove(ctx,packageName)}
func (p *Provider) ResidueAudit(ctx context.Context,_ model.ServiceState)(map[string]string,error){out:=map[string]string{"customer_data":"preserved"};r,_:=p.Runner.Run(ctx,"/usr/bin/rpm","-q",packageName);if r.ExitCode==0{out["rpm"]="present"}else{out["rpm"]="absent"};r,_=p.Runner.Run(ctx,"/usr/bin/systemctl","is-active",serviceUnit);if r.ExitCode==0{out["service"]="active"}else{out["service"]="inactive"};if _,err:=os.Lstat(ownerPath);err==nil{out["owner"]="present"}else{out["owner"]="absent"};return out,nil}

func ensureOwnerAvailable(serviceID string)error{raw,err:=os.ReadFile(ownerPath);if errors.Is(err,os.ErrNotExist){return nil};if err!=nil{return err};if strings.TrimSpace(string(raw))!=serviceID{return errors.New("tomcat is already owned by another service")};return nil}
func claimOwner(serviceID string)error{if err:=ensureOwnerAvailable(serviceID);err!=nil{return err};return filesystem.AtomicWrite(ownerPath,[]byte(serviceID+"\n"),0600,"/var/lib/layersentryd/state")}

func rewriteConnector(ip string,port int,restore bool)error{
    raw,err:=os.ReadFile(serverXML);if err!=nil{return err}
    var backup connectorBackup
    if restore{b,err:=os.ReadFile(backupPath);if err!=nil{return err};dec:=json.NewDecoder(bytes.NewReader(b));dec.DisallowUnknownFields();if err=dec.Decode(&backup);err!=nil{return err};if backup.Port==""{return errors.New("invalid Tomcat connector backup")}}
    dec:=xml.NewDecoder(bytes.NewReader(raw));var out bytes.Buffer;enc:=xml.NewEncoder(&out);matches:=0
    for{tok,err:=dec.RawToken();if errors.Is(err,io.EOF){break};if err!=nil{return fmt.Errorf("parse Tomcat server.xml: %w",err)};if start,ok:=tok.(xml.StartElement);ok&&start.Name.Local=="Connector"&&isHTTPConnector(start){matches++;if matches>1{return errors.New("multiple Tomcat HTTP connectors found; refusing ambiguous rewrite")};if restore{start=restoreConnector(start,backup)}else{var original connectorBackup;start,original=manageConnector(start,ip,port);if _,err=os.Lstat(backupPath);errors.Is(err,os.ErrNotExist){b,_:=json.MarshalIndent(original,"","  ");if err=filesystem.AtomicWrite(backupPath,append(b,'\n'),0600,"/var/lib/layersentryd/state");err!=nil{return err}}else if err!=nil{return err}};tok=start};if err=enc.EncodeToken(tok);err!=nil{return err}}
    if matches!=1{return errors.New("exactly one Tomcat HTTP connector is required")};if err=enc.Flush();err!=nil{return err};if err=filesystem.AtomicWrite(serverXML,out.Bytes(),0644,"/etc/tomcat");err!=nil{return err};if restore{if err=os.Remove(backupPath);err!=nil&&!errors.Is(err,os.ErrNotExist){return err}};return validateServerXML()
}
func isHTTPConnector(s xml.StartElement)bool{port:="";protocol:="";for _,a:=range s.Attr{switch a.Name.Local{case "port":port=a.Value;case "protocol":protocol=a.Value}};if port==""{return false};return protocol==""||strings.Contains(strings.ToUpper(protocol),"HTTP")}
func manageConnector(s xml.StartElement,ip string,port int)(xml.StartElement,connectorBackup){b:=connectorBackup{};hasAddress:=false;for i,a:=range s.Attr{switch a.Name.Local{case "port":b.Port=a.Value;s.Attr[i].Value=fmt.Sprintf("%d",port);case "address":b.Address=a.Value;b.HadAddress=true;hasAddress=true;s.Attr[i].Value=ip}};if !hasAddress{s.Attr=append(s.Attr,xml.Attr{Name:xml.Name{Local:"address"},Value:ip})};return s,b}
func restoreConnector(s xml.StartElement,b connectorBackup)xml.StartElement{out:=make([]xml.Attr,0,len(s.Attr));addressRestored:=false;for _,a:=range s.Attr{switch a.Name.Local{case "port":a.Value=b.Port;out=append(out,a);case "address":if b.HadAddress{a.Value=b.Address;out=append(out,a);addressRestored=true};default:out=append(out,a)}};if b.HadAddress&&!addressRestored{out=append(out,xml.Attr{Name:xml.Name{Local:"address"},Value:b.Address})};s.Attr=out;return s}
func validateServerXML()error{raw,err:=os.ReadFile(serverXML);if err!=nil{return err};dec:=xml.NewDecoder(bytes.NewReader(raw));for{_,err=dec.Token();if errors.Is(err,io.EOF){return nil};if err!=nil{return fmt.Errorf("invalid Tomcat server.xml after rewrite: %w",err)}}}
