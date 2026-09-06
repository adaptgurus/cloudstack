package main

import (
 "encoding/json"
 "fmt"
 "os"
 "strings"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/config"
)

func main(){if len(os.Args)<2{usage();os.Exit(2)};switch os.Args[1]{case "validate-config":if len(os.Args)!=3{usage();os.Exit(2)};b,err:=os.ReadFile(os.Args[2]);fatal(err);req,err:=config.DecodeStrict(b);fatal(err);d,err:=config.CanonicalDigest(req);fatal(err);fmt.Printf("VALID config_digest=%s service_id=%s provider=%s\n",d,req.ServiceID,req.Provider);case "bootstrap-token":b,err:=os.ReadFile("/var/lib/layersentryd/identity/bootstrap-token");fatal(err);fmt.Print(strings.TrimSpace(string(b)),"\n");case "export-config":if len(os.Args)!=3{usage();os.Exit(2)};b,err:=os.ReadFile(os.Args[2]);fatal(err);var v any;fatal(json.Unmarshal(b,&v));enc:=json.NewEncoder(os.Stdout);enc.SetIndent("","  ");fatal(enc.Encode(v));default:usage();os.Exit(2)}}
func usage(){fmt.Fprintln(os.Stderr,"usage: layersentryctl validate-config FILE | bootstrap-token | export-config FILE")}
func fatal(err error){if err!=nil{fmt.Fprintln(os.Stderr,"layersentryctl:",err);os.Exit(1)}}
