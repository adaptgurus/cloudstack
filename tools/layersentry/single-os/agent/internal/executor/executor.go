package executor

import (
 "bytes"
 "context"
 "errors"
 "fmt"
 "os"
 "os/exec"
 "strings"
 "time"
)

type Result struct{ Stdout string; Stderr string; ExitCode int }
type Runner interface{ Run(context.Context,string,...string)(Result,error) }
type OSRunner struct{ Timeout time.Duration; MaxOutput int }
func (r OSRunner)Run(ctx context.Context, exe string,args ...string)(Result,error){
 if !strings.HasPrefix(exe,"/"){return Result{},errors.New("executable must be absolute")}
 if r.Timeout<=0{r.Timeout=2*time.Minute};if r.MaxOutput<=0{r.MaxOutput=1<<20}
 cctx,cancel:=context.WithTimeout(ctx,r.Timeout);defer cancel();cmd:=exec.CommandContext(cctx,exe,args...);cmd.Env=[]string{"PATH=/usr/sbin:/usr/bin:/sbin:/bin","LANG=C.UTF-8","LC_ALL=C.UTF-8"}
 var out,er bytes.Buffer;cmd.Stdout=&limitedWriter{w:&out,n:r.MaxOutput};cmd.Stderr=&limitedWriter{w:&er,n:r.MaxOutput};err:=cmd.Run();res:=Result{Stdout:out.String(),Stderr:er.String(),ExitCode:0}
 if cctx.Err()!=nil{return res,cctx.Err()};if err!=nil{var ee *exec.ExitError;if errors.As(err,&ee){res.ExitCode=ee.ExitCode()};return res,fmt.Errorf("%s failed: exit=%d",exe,res.ExitCode)};return res,nil
}
type limitedWriter struct{w *bytes.Buffer;n int}
func(l *limitedWriter)Write(p []byte)(int,error){orig:=len(p);if l.n<=0{return orig,nil};if len(p)>l.n{p=p[:l.n]};_,_=l.w.Write(p);l.n-=len(p);return orig,nil}
func WriteStdinFile(path string,data []byte)error{f,err:=os.OpenFile(path,os.O_WRONLY,0);if err!=nil{return err};defer f.Close();_,err=f.Write(data);return err}
