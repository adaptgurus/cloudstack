package lock

import (
 "errors"
 "os"
 "path/filepath"
 "syscall"
)

type MutationLock struct{ f *os.File }
func Acquire(path string)(*MutationLock,error){
 if !filepath.IsAbs(path){return nil,errors.New("lock path must be absolute")}
 if err:=os.MkdirAll(filepath.Dir(path),0700);err!=nil{return nil,err}
 f,err:=os.OpenFile(path,os.O_CREATE|os.O_RDWR,0600);if err!=nil{return nil,err}
 if err=syscall.Flock(int(f.Fd()),syscall.LOCK_EX|syscall.LOCK_NB);err!=nil{f.Close();return nil,errors.New("another lifecycle mutation is already running")}
 return &MutationLock{f:f},nil
}
func(l *MutationLock)Release()error{if l==nil||l.f==nil{return nil};_ = syscall.Flock(int(l.f.Fd()),syscall.LOCK_UN);return l.f.Close()}
