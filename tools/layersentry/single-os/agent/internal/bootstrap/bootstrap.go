package bootstrap

import (
 "crypto/rand"
 "crypto/rsa"
 "crypto/x509"
 "crypto/x509/pkix"
 "encoding/hex"
 "encoding/pem"
 "errors"
 "fmt"
 "math/big"
 "net"
 "os"
 "path/filepath"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
)

type Paths struct{Root,NodeID,BootstrapToken,TLSCert,TLSKey string}
func DefaultPaths()Paths{return Paths{Root:"/var/lib/layersentryd",NodeID:"/var/lib/layersentryd/identity/node-id",BootstrapToken:"/var/lib/layersentryd/identity/bootstrap-token",TLSCert:"/var/lib/layersentryd/identity/tls.crt",TLSKey:"/var/lib/layersentryd/identity/tls.key"}}
func Ensure(p Paths,ips []net.IP)error{if !filepath.IsAbs(p.Root){return errors.New("bootstrap root must be absolute")};identity:=filepath.Join(p.Root,"identity");if err:=privateDir(identity);err!=nil{return err};if err:=ensureRandomHex(p.NodeID,16,identity);err!=nil{return err};if err:=ensureRandomHex(p.BootstrapToken,32,identity);err!=nil{return err};if fi,err:=os.Lstat(p.TLSKey);err==nil{if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular(){return errors.New("unsafe TLS key path")};cert,err:=os.Lstat(p.TLSCert);if err!=nil||cert.Mode()&os.ModeSymlink!=0||!cert.Mode().IsRegular(){return errors.New("TLS key exists without safe certificate")}}else if errors.Is(err,os.ErrNotExist){if err=generateTLS(p.TLSCert,p.TLSKey,ips,identity);err!=nil{return err}}else{return err};return nil}
func privateDir(path string)error{if err:=os.MkdirAll(path,0700);err!=nil{return err};fi,err:=os.Lstat(path);if err!=nil{return err};if !fi.IsDir()||fi.Mode()&os.ModeSymlink!=0||fi.Mode().Perm()&0022!=0{return errors.New("bootstrap directory must be private and non-symlink")};return nil}
func ensureRandomHex(path string,n int,root string)error{if fi,err:=os.Lstat(path);err==nil{if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular(){return errors.New("unsafe bootstrap identity path")};return nil}else if !errors.Is(err,os.ErrNotExist){return err};b:=make([]byte,n);if _,err:=rand.Read(b);err!=nil{return err};return filesystem.AtomicWrite(path,[]byte(hex.EncodeToString(b)+"\n"),0600,root)}
func generateTLS(certPath,keyPath string,ips []net.IP,root string)error{key,err:=rsa.GenerateKey(rand.Reader,3072);if err!=nil{return err};serialLimit:=new(big.Int).Lsh(big.NewInt(1),128);serial,err:=rand.Int(rand.Reader,serialLimit);if err!=nil{return err};now:=time.Now().UTC();tmpl:=x509.Certificate{SerialNumber:serial,Subject:pkix.Name{CommonName:"LayerSentry Single-OS"},NotBefore:now.Add(-5*time.Minute),NotAfter:now.Add(397*24*time.Hour),KeyUsage:x509.KeyUsageDigitalSignature|x509.KeyUsageKeyEncipherment,ExtKeyUsage:[]x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},BasicConstraintsValid:true,IPAddresses:ips,DNSNames:[]string{"localhost"}};der,err:=x509.CreateCertificate(rand.Reader,&tmpl,&tmpl,&key.PublicKey,key);if err!=nil{return err};cert:=pem.EncodeToMemory(&pem.Block{Type:"CERTIFICATE",Bytes:der});priv:=pem.EncodeToMemory(&pem.Block{Type:"RSA PRIVATE KEY",Bytes:x509.MarshalPKCS1PrivateKey(key)});if err=filesystem.AtomicWrite(certPath,cert,0644,root);err!=nil{return err};return filesystem.AtomicWrite(keyPath,priv,0600,root)}
func Seal(p Paths)error{if !filepath.IsAbs(p.Root){return errors.New("seal root must be absolute")};customerPaths:=[]string{"state/services","operations","plans","checkpoints","secrets","evidence","backups","apps"};if exists(filepath.Join(p.Root,"identity","admin.json")){return errors.New("refusing to seal image with initialized administrator")};for _,dir:=range customerPaths{path:=filepath.Join(p.Root,dir);entries,err:=os.ReadDir(path);if err==nil&&len(entries)>0{return fmt.Errorf("refusing to seal image with customer lifecycle state in %s",path)};if err!=nil&&!errors.Is(err,os.ErrNotExist){return err}};for _,path:=range []string{p.NodeID,p.BootstrapToken,p.TLSCert,p.TLSKey,filepath.Join(p.Root,"identity","secret.key"),filepath.Join(p.Root,"identity","admin.json")}{if err:=os.Remove(path);err!=nil&&!errors.Is(err,os.ErrNotExist){return err}};for _,dir:=range customerPaths{path:=filepath.Join(p.Root,dir);if err:=os.RemoveAll(path);err!=nil{return err}};return nil}
func exists(path string)bool{_,err:=os.Lstat(path);return err==nil}
