package secrets

import (
 "crypto/aes"
 "crypto/cipher"
 "crypto/rand"
 "encoding/hex"
 "errors"
 "io"
 "os"
 "path/filepath"
 "strings"
)

type Store struct{root,keyPath string;key []byte}
func Open(root,keyPath string)(*Store,error){if !filepath.IsAbs(root)||!filepath.IsAbs(keyPath){return nil,errors.New("secret paths must be absolute")};if err:=os.MkdirAll(root,0700);err!=nil{return nil,err};key,err:=loadOrCreateKey(keyPath);if err!=nil{return nil,err};return &Store{root:root,keyPath:keyPath,key:key},nil}
func loadOrCreateKey(path string)([]byte,error){if b,err:=os.ReadFile(path);err==nil{if len(b)!=32{return nil,errors.New("invalid secret key length")};return b,nil};if err:=os.MkdirAll(filepath.Dir(path),0700);err!=nil{return nil,err};b:=make([]byte,32);if _,err:=io.ReadFull(rand.Reader,b);err!=nil{return nil,err};f,err:=os.OpenFile(path,os.O_CREATE|os.O_EXCL|os.O_WRONLY,0600);if err!=nil{return nil,err};if _,err=f.Write(b);err!=nil{f.Close();return nil,err};if err=f.Sync();err!=nil{f.Close();return nil,err};return b,f.Close()}
func (s *Store)Put(value []byte)(string,error){if len(value)==0||len(value)>1<<20{return "",errors.New("secret size invalid")};idb:=make([]byte,16);if _,err:=io.ReadFull(rand.Reader,idb);err!=nil{return "",err};id:=hex.EncodeToString(idb);block,err:=aes.NewCipher(s.key);if err!=nil{return "",err};gcm,err:=cipher.NewGCM(block);if err!=nil{return "",err};nonce:=make([]byte,gcm.NonceSize());if _,err=io.ReadFull(rand.Reader,nonce);err!=nil{return "",err};ct:=gcm.Seal(nil,nonce,value,[]byte(id));payload:=append(nonce,ct...);path:=filepath.Join(s.root,id+".bin");if err=os.WriteFile(path,payload,0600);err!=nil{return "",err};return "secret://"+id,nil}
func(s *Store)Get(ref string)([]byte,error){if !strings.HasPrefix(ref,"secret://"){return nil,errors.New("invalid secret reference")};id:=strings.TrimPrefix(ref,"secret://");if len(id)!=32{return nil,errors.New("invalid secret id")};path:=filepath.Join(s.root,id+".bin");fi,err:=os.Lstat(path);if err!=nil{return nil,err};if fi.Mode()&os.ModeSymlink!=0||fi.Size()>2<<20{return nil,errors.New("unsafe secret object")};payload,err:=os.ReadFile(path);if err!=nil{return nil,err};block,err:=aes.NewCipher(s.key);if err!=nil{return nil,err};gcm,err:=cipher.NewGCM(block);if err!=nil{return nil,err};if len(payload)<gcm.NonceSize(){return nil,errors.New("truncated secret")};return gcm.Open(nil,payload[:gcm.NonceSize()],payload[gcm.NonceSize():],[]byte(id))}
