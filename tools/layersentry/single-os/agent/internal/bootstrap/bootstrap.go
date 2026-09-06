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
)

type Paths struct{Root,NodeID,BootstrapToken,TLSCert,TLSKey string}
func DefaultPaths()Paths{return Paths{Root:"/var/lib/layersentryd",NodeID:"/var/lib/layersentryd/identity/node-id",BootstrapToken:"/var/lib/layersentryd/identity/bootstrap-token",TLSCert:"/var/lib/layersentryd/identity/tls.crt",TLSKey:"/var/lib/layersentryd/identity/tls.key"}}
func Ensure(p Paths,ips []net.IP)error{if err:=os.MkdirAll(filepath.Join(p.Root,"identity"),0700);err!=nil{return err};if err:=ensureRandomHex(p.NodeID,16);err!=nil{return err};if err:=ensureRandomHex(p.BootstrapToken,32);err!=nil{return err};if _,err:=os.Stat(p.TLSKey);errors.Is(err,os.ErrNotExist){if err=generateTLS(p.TLSCert,p.TLSKey,ips);err!=nil{return err}};return nil}
func ensureRandomHex(path string,n int)error{if _,err:=os.Stat(path);err==nil{return nil};b:=make([]byte,n);if _,err:=rand.Read(b);err!=nil{return err};return os.WriteFile(path,[]byte(hex.EncodeToString(b)+"\n"),0600)}
func generateTLS(certPath,keyPath string,ips []net.IP)error{key,err:=rsa.GenerateKey(rand.Reader,3072);if err!=nil{return err};serialLimit:=new(big.Int).Lsh(big.NewInt(1),128);serial,err:=rand.Int(rand.Reader,serialLimit);if err!=nil{return err};now:=time.Now().UTC();tmpl:=x509.Certificate{SerialNumber:serial,Subject:pkix.Name{CommonName:"LayerSentry Single-OS"},NotBefore:now.Add(-5*time.Minute),NotAfter:now.Add(397*24*time.Hour),KeyUsage:x509.KeyUsageDigitalSignature|x509.KeyUsageKeyEncipherment,ExtKeyUsage:[]x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},BasicConstraintsValid:true,IPAddresses:ips,DNSNames:[]string{"localhost"}};der,err:=x509.CreateCertificate(rand.Reader,&tmpl,&tmpl,&key.PublicKey,key);if err!=nil{return err};cert:=pem.EncodeToMemory(&pem.Block{Type:"CERTIFICATE",Bytes:der});priv:=pem.EncodeToMemory(&pem.Block{Type:"RSA PRIVATE KEY",Bytes:x509.MarshalPKCS1PrivateKey(key)});if err=os.WriteFile(certPath,cert,0644);err!=nil{return err};return os.WriteFile(keyPath,priv,0600)}
func Seal(p Paths)error{if exists(filepath.Join(p.Root,"identity","admin.json")){return errors.New("refusing to seal image with initialized administrator")};for _,dir:=range []string{"state/services","operations","plans"}{path:=filepath.Join(p.Root,dir);entries,err:=os.ReadDir(path);if err==nil&&len(entries)>0{return fmt.Errorf("refusing to seal image with customer lifecycle state in %s",path)};if err!=nil&&!errors.Is(err,os.ErrNotExist){return err}};for _,path:=range []string{p.NodeID,p.BootstrapToken,p.TLSCert,p.TLSKey,filepath.Join(p.Root,"identity","secret.key")}{if err:=os.Remove(path);err!=nil&&!errors.Is(err,os.ErrNotExist){return err}};for _,dir:=range []string{"operations","plans","state/services","checkpoints","secrets","evidence","backups"}{path:=filepath.Join(p.Root,dir);if err:=os.RemoveAll(path);err!=nil{return err}};return nil}
func exists(path string)bool{_,err:=os.Lstat(path);return err==nil}
