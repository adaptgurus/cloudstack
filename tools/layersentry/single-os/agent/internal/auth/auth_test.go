package auth

import (
    "os"
    "path/filepath"
    "testing"
)

func TestBootstrapIsOneTimeAndLoginWorks(t *testing.T){dir:=t.TempDir();tokenPath:=filepath.Join(dir,"bootstrap");adminPath:=filepath.Join(dir,"admin.json");if err:=os.WriteFile(tokenPath,[]byte("one-time-token\n"),0600);err!=nil{t.Fatal(err)};m:=New(adminPath);if err:=m.Bootstrap(tokenPath,"adminuser","a-strong-password-for-test","one-time-token");err==nil{t.Fatal("argument order regression should not silently bootstrap")}}
func TestBootstrapLoginLogout(t *testing.T){dir:=t.TempDir();tokenPath:=filepath.Join(dir,"bootstrap");adminPath:=filepath.Join(dir,"admin.json");if err:=os.WriteFile(tokenPath,[]byte("one-time-token\n"),0600);err!=nil{t.Fatal(err)};m:=New(adminPath);if err:=m.Bootstrap(tokenPath,"one-time-token","adminuser","a-strong-password-for-test");err!=nil{t.Fatal(err)};if _,err:=os.Stat(tokenPath);!os.IsNotExist(err){t.Fatal("bootstrap token was not invalidated")};token,_,err:=m.Login("adminuser","a-strong-password-for-test");if err!=nil{t.Fatal(err)};if !m.Valid(token){t.Fatal("new session should be valid")};m.Logout(token);if m.Valid(token){t.Fatal("logged-out session remained valid")};if err:=m.Bootstrap(tokenPath,"one-time-token","otheruser","another-strong-password");err==nil{t.Fatal("second bootstrap should fail")}}
func TestLoginRejectsBadPassword(t *testing.T){dir:=t.TempDir();tokenPath:=filepath.Join(dir,"bootstrap");adminPath:=filepath.Join(dir,"admin.json");_ = os.WriteFile(tokenPath,[]byte("token\n"),0600);m:=New(adminPath);if err:=m.Bootstrap(tokenPath,"token","adminuser","a-strong-password-for-test");err!=nil{t.Fatal(err)};if _,_,err:=m.Login("adminuser","wrong-password-value");err==nil{t.Fatal("bad password accepted")}}
