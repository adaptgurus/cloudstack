package main

import "os"

func init(){
    if len(os.Args)<2{return}
    switch os.Args[1]{
    case "plan-file":
        if len(os.Args)!=3{must(errUsage("plan-file requires exactly one JSON intent file"))}
        must(planFile(os.Args[2]));os.Exit(0)
    case "apply-file":
        if len(os.Args)!=4{must(errUsage("apply-file requires JSON intent file and confirmed plan digest"))}
        must(applyFile(os.Args[2],os.Args[3]));os.Exit(0)
    }
}
type usageError string
func(e usageError)Error()string{return string(e)}
func errUsage(s string)error{return usageError(s)}
