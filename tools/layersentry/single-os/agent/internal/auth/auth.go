package auth

import (
 "crypto/rand"
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "errors"
 "os"
 "path/filepath"
 "sync"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
 "golang.org/x/crypto/bcrypt"
)

const maxSessions=128
type adminRecord struct{Username string `json:"username"`;PasswordHash string `json:"password_hash"`;CreatedAt time.Time `json:"created_at"`}
type session struct{Expires time.Time}
type Manager struct{path string;mu sync.Mutex;sessions map[[32]byte]session}
func New(path string)*Manager{return &Manager{path:path,sessions:map[[32]byte]session{}}}
func(m *Manager)Initialized()bool{fi,err:=os.Lstat(m.path);return err==nil&&fi.Mode().IsRegular()&&fi.Mode()&os.ModeSymlink==0}
func(m *Manager)Bootstrap(bootstrapFile,token,username,password string)error{if m.Initialized(){return errors.New("administrator already initialized")};if fi,err:=os.Lstat(m.path);err==nil&&(fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular()){return errors.New("unsafe administrator record path")};expected,err:=os.ReadFile(bootstrapFile);if err!=nil{return err};if !subtleEqual(stringTrim(expected),token){return errors.New("invalid bootstrap token")};if len(username)<3||len(username)>64||len(password)<14||len(password)>256{return errors.New("username/password policy failed")};h,err:=bcrypt.GenerateFromPassword([]byte(password),bcrypt.DefaultCost);if err!=nil{return err};rec:=adminRecord{Username:username,PasswordHash:string(h),CreatedAt:time.Now().UTC()};b,err:=json.Marshal(rec);if err!=nil{return err};root:=filepath.Dir(m.path);if err=filesystem.AtomicWrite(m.path,b,0600,root);err!=nil{return err};return os.Remove(bootstrapFile)}
func(m *Manager)Login(username,password string)(string,time.Time,error){fi,err:=os.Lstat(m.path);if err!=nil{return "",time.Time{},err};if fi.Mode()&os.ModeSymlink!=0||!fi.Mode().IsRegular()||fi.Size()>64<<10{return "",time.Time{},errors.New("unsafe administrator record")};b,err:=os.ReadFile(m.path);if err!=nil{return "",time.Time{},err};var rec adminRecord;if err=json.Unmarshal(b,&rec);err!=nil{return "",time.Time{},err};if username!=rec.Username||bcrypt.CompareHashAndPassword([]byte(rec.PasswordHash),[]byte(password))!=nil{return "",time.Time{},errors.New("invalid credentials")};raw:=make([]byte,32);if _,err=rand.Read(raw);err!=nil{return "",time.Time{},err};sum:=sha256.Sum256(raw);exp:=time.Now().UTC().Add(8*time.Hour);m.mu.Lock();defer m.mu.Unlock();now:=time.Now().UTC();for k,s:=range m.sessions{if now.After(s.Expires){delete(m.sessions,k)}};if len(m.sessions)>=maxSessions{return "",time.Time{},errors.New("session limit reached")};m.sessions[sum]=session{Expires:exp};return hex.EncodeToString(raw),exp,nil}
func(m *Manager)Valid(token string)bool{raw,err:=hex.DecodeString(token);if err!=nil||len(raw)!=32{return false};sum:=sha256.Sum256(raw);m.mu.Lock();defer m.mu.Unlock();s,ok:=m.sessions[sum];if !ok{return false};if time.Now().UTC().After(s.Expires){delete(m.sessions,sum);return false};return true}
func(m *Manager)Logout(token string){raw,err:=hex.DecodeString(token);if err!=nil{return};sum:=sha256.Sum256(raw);m.mu.Lock();delete(m.sessions,sum);m.mu.Unlock()}
func stringTrim(b []byte)string{n:=len(b);for n>0&&(b[n-1]=='\n'||b[n-1]=='\r'||b[n-1]==' '){n--};return string(b[:n])}
func subtleEqual(a,b string)bool{if len(a)!=len(b){return false};var v byte;for i:=0;i<len(a);i++{v|=a[i]^b[i]};return v==0}
