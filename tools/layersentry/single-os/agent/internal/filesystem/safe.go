package filesystem

import (
 "errors"
 "fmt"
 "os"
 "path/filepath"
 "strings"
)

func EnsureUnder(path string,roots ...string)(string,error){if !filepath.IsAbs(path){return "",errors.New("path must be absolute")};clean:=filepath.Clean(path);for _,root:=range roots{r:=filepath.Clean(root);rel,err:=filepath.Rel(r,clean);if err==nil&&rel!=".."&&!strings.HasPrefix(rel,".."+string(os.PathSeparator)){return clean,nil}};return "",fmt.Errorf("path %q outside approved roots",path)}
func AtomicWrite(path string,data []byte,mode os.FileMode,roots ...string)error{clean,err:=EnsureUnder(path,roots...);if err!=nil{return err};dir:=filepath.Dir(clean);if fi,err:=os.Lstat(dir);err!=nil{return err}else if fi.Mode()&os.ModeSymlink!=0{return errors.New("parent directory is symlink")};if fi,err:=os.Lstat(clean);err==nil&&fi.Mode()&os.ModeSymlink!=0{return errors.New("target is symlink")};f,err:=os.CreateTemp(dir,".layersentry-*");if err!=nil{return err};tmp:=f.Name();defer os.Remove(tmp);if err=f.Chmod(mode);err!=nil{f.Close();return err};if _,err=f.Write(data);err!=nil{f.Close();return err};if err=f.Sync();err!=nil{f.Close();return err};if err=f.Close();err!=nil{return err};return os.Rename(tmp,clean)}
