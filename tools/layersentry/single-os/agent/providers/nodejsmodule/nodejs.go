package nodejsmodule

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/packageutil"
)

const(
	providerID="nodejs-runtime"
	packageName="nodejs"
	repoID="appstream"
	moduleSpec="nodejs:20"
	moduleStream="20"
	ownerPath="/var/lib/layersentryd/state/nodejs-module-owner"
)
var node20NEVRA=regexp.MustCompile(`^nodejs-(?:[0-9]+:)?20\.[A-Za-z0-9._+~:-]+$`)
type Provider struct{Runner executor.Runner;DNF packageutil.DNF}
func New(r executor.Runner)*Provider{return &Provider{Runner:r,DNF:packageutil.DNF{Runner:r}}}
func(p *Provider)ID()string{return providerID}
func(p *Provider)Category()model.Category{return model.CategoryApplication}
func(p *Provider)Validate(ctx context.Context,r model.ServiceRequest)error{if r.Category!=model.CategoryApplication{return errors.New("Node.js runtime category must be application")};if r.Topology!="standalone"{return errors.New("Node.js runtime supports standalone package lifecycle only")};if r.ReleaseLine!="20"{return errors.New("qualified Node.js release line is 20; newer Rocky/RHEL streams remain technology-preview until separately approved")};if r.Network.Port!=0||r.Network.ListenAddress!=""||len(r.Network.AllowedCIDRs)!=0{return errors.New("Node.js runtime provider does not own a network listener")};if r.Backup.Enabled||r.Backup.Schedule!=""||r.Backup.Retention!=0{return errors.New("Node.js runtime provider does not own customer application-data backup")};if len(r.Storage)!=0{return errors.New("Node.js runtime provider does not consume attached storage")};if len(r.SecretRefs)!=0{return errors.New("Node.js runtime provider does not consume secret references")};if raw,err:=os.ReadFile(ownerPath);err==nil&&strings.TrimSpace(string(raw))!=r.ServiceID{return errors.New("LayerSentry Node.js module stream is already owned by another service")}else if err!=nil&&!errors.Is(err,os.ErrNotExist){return err};stream,err:=p.enabledStream(ctx);if err!=nil{return err};if stream!=""&&stream!=moduleStream{return fmt.Errorf("different Node.js module stream %q is already enabled",stream)};rpm,err:=p.Runner.Run(ctx,"/usr/bin/rpm","-q",packageName);if err==nil&&rpm.ExitCode==0{if raw,ownerErr:=os.ReadFile(ownerPath);ownerErr!=nil||strings.TrimSpace(string(raw))!=r.ServiceID{return errors.New("refusing to adopt a pre-existing unmanaged Node.js installation")}};return nil}
func(p *Provider)ResolveVersion(ctx context.Context,_ model.ServiceRequest)(string,error){if err:=p.DNF.ValidateRepositories(ctx,repoID);err!=nil{return "",err};res,err:=p.Runner.Run(ctx,"/usr/bin/dnf","-q","module","repoquery","--available",moduleSpec);if err!=nil{return "",err};var candidates []string;for _,f:=range strings.Fields(res.Stdout){if node20NEVRA.MatchString(f){candidates=append(candidates,f)}};if len(candidates)==0{return "",errors.New("Node.js 20 module stream exposes no exact nodejs package")};sort.Strings(candidates);return candidates[len(candidates)-1],nil}
func(p *Provider)Plan(ctx context.Context,r model.ServiceRequest,resolved string)(model.Plan,error){if !node20NEVRA.MatchString(resolved){return model.Plan{},errors.New("Node.js resolved package is outside stream 20")};repoDigest,err:=p.DNF.RepositoryDigest(ctx,repoID);if err!=nil{return model.Plan{},err};stream,err:=p.enabledStream(ctx);if err!=nil{return model.Plan{},err};moduleAction:="use already-enabled nodejs:20 module stream";if stream==""{moduleAction="enable nodejs:20 module stream only after explicit plan confirmation"};steps:=[]model.PlanStep{{Name:"repository",Action:"use Rocky AppStream with GPG/TLS verification"},{Name:"module-stream",Action:moduleAction},{Name:"packages",Action:"install exact supported Node.js 20 package "+resolved},{Name:"runtime-health",Action:"verify installed Node.js RPM identity; customer workload remains separately managed"}};sum:=sha256.Sum256([]byte(fmt.Sprintf("%s|%s|%s|%s|%s|%s|%v",r.ServiceID,providerID,resolved,repoID,repoDigest,moduleStream,steps)));return model.Plan{ID:r.OperationID,ServiceID:r.ServiceID,Provider:p.ID(),ResolvedVersion:resolved,RepositoryID:repoID,RepositoryDigest:repoDigest,Digest:hex.EncodeToString(sum[:]),CreatedAt:time.Now().UTC(),Request:r,Steps:steps},nil}
func(p *Provider)Install(ctx context.Context,_ model.Operation,plan model.Plan)error{if !node20NEVRA.MatchString(plan.ResolvedVersion)||plan.RepositoryID!=repoID||plan.RepositoryDigest==""{return errors.New("Node.js plan provenance invalid")};digest,err:=p.DNF.RepositoryDigest(ctx,repoID);if err!=nil{return err};if digest!=plan.RepositoryDigest{return errors.New("Node.js AppStream repository drifted after plan confirmation")};stream,err:=p.enabledStream(ctx);if err!=nil{return err};if stream!=""&&stream!=moduleStream{return fmt.Errorf("different Node.js module stream %q became enabled",stream)};enabledByUs:=false;if stream==""{if _,err=p.Runner.Run(ctx,"/usr/bin/dnf","-y","module","enable",moduleSpec);err!=nil{return err};if err=filesystem.AtomicWrite(ownerPath,[]byte(plan.ServiceID+"\n"),0600,"/var/lib/layersentryd/state");err!=nil{_,_=p.Runner.Run(ctx,"/usr/bin/dnf","-y","module","reset","nodejs");return err};enabledByUs=true};if err=p.DNF.InstallExactFromRepos(ctx,[]string{repoID},plan.ResolvedVersion);err!=nil{if enabledByUs{_,_=p.Runner.Run(ctx,"/usr/bin/dnf","-y","module","reset","nodejs");_ = os.Remove(ownerPath)};return err};return nil}
func(p *Provider)Configure(context.Context,model.Operation,model.Plan)error{return nil}
func(p *Provider)Initialize(context.Context,model.Operation,model.Plan)error{return nil}
func(p *Provider)Join(context.Context,model.Operation,model.Plan)error{return errors.New("Node.js runtime cluster join is not supported")}
func(p *Provider)Health(ctx context.Context,_ model.ServiceState)(model.HealthResult,error){r,err:=p.Runner.Run(ctx,"/usr/bin/rpm","-q",packageName);if err!=nil{return model.HealthResult{Healthy:false,Checks:map[string]string{"rpm":"missing"},Error:"Node.js runtime package is not installed"},nil};version:=strings.TrimSpace(r.Stdout);return model.HealthResult{Healthy:version!="",Version:version,Checks:map[string]string{"rpm":"installed","module_stream":"20","workload":"not-managed-by-runtime-provider"}},nil}
func(p *Provider)Start(context.Context,model.Operation,model.ServiceState)error{return nil}
func(p *Provider)Stop(context.Context,model.Operation,model.ServiceState)error{return nil}
func(p *Provider)Restart(context.Context,model.Operation,model.ServiceState)error{return nil}
func(p *Provider)Upgrade(ctx context.Context,op model.Operation,plan model.Plan)error{return p.Install(ctx,op,plan)}
func(p *Provider)Repair(ctx context.Context,_ model.Operation,_ model.Plan)error{_,err:=p.Runner.Run(ctx,"/usr/bin/rpm","-q",packageName);return err}
func(p *Provider)Backup(context.Context,model.Operation,model.ServiceState)(model.BackupRecord,error){return model.BackupRecord{},errors.New("Node.js runtime provider does not own customer application-data backup")}
func(p *Provider)Restore(context.Context,model.Operation,model.ServiceState,model.BackupRecord)error{return errors.New("Node.js runtime provider does not own customer application-data restore")}
func(p *Provider)Uninstall(ctx context.Context,_ model.Operation,st model.ServiceState,destroyData bool)error{if destroyData{return errors.New("Node.js runtime uninstall never destroys customer application data")};if err:=p.DNF.Remove(ctx,packageName);err!=nil{return err};raw,err:=os.ReadFile(ownerPath);if errors.Is(err,os.ErrNotExist){return nil};if err!=nil{return err};if strings.TrimSpace(string(raw))!=st.ID{return errors.New("Node.js module ownership changed; refusing module reset")};if _,err=p.Runner.Run(ctx,"/usr/bin/dnf","-y","module","reset","nodejs");err!=nil{return err};return os.Remove(ownerPath)}
func(p *Provider)ResidueAudit(ctx context.Context,st model.ServiceState)(map[string]string,error){out:=map[string]string{"customer_data":"preserved"};r,_:=p.Runner.Run(ctx,"/usr/bin/rpm","-q",packageName);if r.ExitCode==0{out["rpm"]="present"}else{out["rpm"]="absent"};if raw,err:=os.ReadFile(ownerPath);err==nil&&strings.TrimSpace(string(raw))==st.ID{out["module_owner"]="present"}else{out["module_owner"]="absent"};return out,nil}
func(p *Provider)enabledStream(ctx context.Context)(string,error){r,err:=p.Runner.Run(ctx,"/usr/bin/dnf","-q","module","list","--enabled","nodejs");if err!=nil{return "",err};for _,line:=range strings.Split(r.Stdout,"\n"){f:=strings.Fields(strings.TrimSpace(line));if len(f)<2||f[0]!="nodejs"{continue};stream:=strings.TrimSpace(strings.SplitN(f[1],"[",2)[0]);if stream!=""{return stream,nil}};return "",nil}
