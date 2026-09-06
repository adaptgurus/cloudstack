package api

import (
 "crypto/rand"
 "encoding/hex"
 "encoding/json"
 "errors"
 "fmt"
 "io"
 "io/fs"
 "net/http"
 "strings"
 "time"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/auth"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/journal"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/lifecycle"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/provider"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/secrets"
 webassets "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/web"
)

type Server struct{Engine *lifecycle.Engine;Auth *auth.Manager;Secrets *secrets.Store;Journal *journal.Store;Registry *provider.Registry;BootstrapFile string;AllowedOrigin string}
func(s *Server)Handler()(http.Handler,error){mux:=http.NewServeMux();mux.HandleFunc("/api/v1/health",s.health);mux.HandleFunc("/api/v1/auth/bootstrap",s.bootstrap);mux.HandleFunc("/api/v1/auth/login",s.login);mux.HandleFunc("/api/v1/auth/logout",s.require(s.logout,true));mux.HandleFunc("/api/v1/appliance",s.require(s.appliance,false));mux.HandleFunc("/api/v1/catalog",s.require(s.catalog,false));mux.HandleFunc("/api/v1/plans",s.require(s.plans,true));mux.HandleFunc("/api/v1/secrets",s.require(s.secretCreate,true));mux.HandleFunc("/api/v1/services",s.require(s.services,false));mux.HandleFunc("/api/v1/services/",s.require(s.serviceRoute,false));mux.HandleFunc("/api/v1/operations/",s.require(s.operationRoute,false));sub,err:=fs.Sub(webassets.Assets,"static");if err!=nil{return nil,err};mux.Handle("/",http.FileServer(http.FS(sub)));return securityHeaders(mux),nil}
func securityHeaders(next http.Handler)http.Handler{return http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){w.Header().Set("X-Content-Type-Options","nosniff");w.Header().Set("X-Frame-Options","DENY");w.Header().Set("Referrer-Policy","no-referrer");w.Header().Set("Content-Security-Policy","default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'");w.Header().Set("Cache-Control","no-store");next.ServeHTTP(w,r)})}
func(s *Server)health(w http.ResponseWriter,r *http.Request){if r.Method!="GET"{method(w);return};write(w,200,map[string]any{"status":"ok","service":"layersentryd","time":time.Now().UTC()})}
func(s *Server)bootstrap(w http.ResponseWriter,r *http.Request){if r.Method!="POST"{method(w);return};var q struct{Token string `json:"token"`;Username string `json:"username"`;Password string `json:"password"`};if err:=decode(r,&q);err!=nil{bad(w,err);return};if err:=s.Auth.Bootstrap(s.BootstrapFile,q.Token,q.Username,q.Password);err!=nil{bad(w,err);return};q.Password="";q.Token="";write(w,201,map[string]string{"status":"administrator-created"})}
func(s *Server)login(w http.ResponseWriter,r *http.Request){if r.Method!="POST"{method(w);return};var q struct{Username string `json:"username"`;Password string `json:"password"`};if err:=decode(r,&q);err!=nil{bad(w,err);return};token,exp,err:=s.Auth.Login(q.Username,q.Password);q.Password="";if err!=nil{http.Error(w,"invalid credentials",http.StatusUnauthorized);return};csrf:=randomHex(24);http.SetCookie(w,&http.Cookie{Name:"layersentry_session",Value:token,Path:"/",Secure:true,HttpOnly:true,SameSite:http.SameSiteStrictMode,Expires:exp});http.SetCookie(w,&http.Cookie{Name:"layersentry_csrf",Value:csrf,Path:"/",Secure:true,HttpOnly:false,SameSite:http.SameSiteStrictMode,Expires:exp});write(w,200,map[string]string{"status":"authenticated","csrf_token":csrf})}
func(s *Server)logout(w http.ResponseWriter,r *http.Request){c,_:=r.Cookie("layersentry_session");if c!=nil{s.Auth.Logout(c.Value)};http.SetCookie(w,&http.Cookie{Name:"layersentry_session",Value:"",Path:"/",Secure:true,HttpOnly:true,MaxAge:-1,SameSite:http.SameSiteStrictMode});http.SetCookie(w,&http.Cookie{Name:"layersentry_csrf",Value:"",Path:"/",Secure:true,MaxAge:-1,SameSite:http.SameSiteStrictMode});write(w,200,map[string]string{"status":"logged-out"})}
func(s *Server)require(next http.HandlerFunc,mutation bool)http.HandlerFunc{return func(w http.ResponseWriter,r *http.Request){c,err:=r.Cookie("layersentry_session");if err!=nil||!s.Auth.Valid(c.Value){http.Error(w,"authentication required",http.StatusUnauthorized);return};if mutation&&r.Method!="GET"&&r.Method!="HEAD"{if err:=s.requireMutationProof(r);err!=nil{http.Error(w,err.Error(),http.StatusForbidden);return}};next(w,r)}}
func(s *Server)appliance(w http.ResponseWriter,r *http.Request){if r.Method!="GET"{method(w);return};write(w,200,map[string]any{"service":"layersentryd","api_version":"v1","admin_initialized":s.Auth.Initialized(),"providers":s.Registry.IDs()})}
func(s *Server)catalog(w http.ResponseWriter,r *http.Request){if r.Method!="GET"{method(w);return};write(w,200,map[string]any{"providers":s.Registry.IDs()})}
func(s *Server)plans(w http.ResponseWriter,r *http.Request){if r.Method!="POST"{method(w);return};var req model.ServiceRequest;if err:=decode(r,&req);err!=nil{bad(w,err);return};plan,op,err:=s.Engine.Plan(r.Context(),req);if err!=nil{bad(w,err);return};write(w,201,map[string]any{"plan":plan,"operation":op})}
func(s *Server)secretCreate(w http.ResponseWriter,r *http.Request){if r.Method!="POST"{method(w);return};var q struct{Value string `json:"value"`};if err:=decode(r,&q);err!=nil{bad(w,err);return};ref,err:=s.Secrets.Put([]byte(q.Value));q.Value="";if err!=nil{bad(w,err);return};write(w,201,map[string]string{"ref":ref})}
func(s *Server)services(w http.ResponseWriter,r *http.Request){if r.Method!="GET"{method(w);return};items,err:=s.Journal.ListServices();if err!=nil{serverErr(w,err);return};write(w,200,map[string]any{"services":items})}
func(s *Server)serviceRoute(w http.ResponseWriter,r *http.Request){tail:=strings.Trim(strings.TrimPrefix(r.URL.Path,"/api/v1/services/"),"/");parts:=strings.Split(tail,"/");if tail==""{http.NotFound(w,r);return};id:=parts[0];if len(parts)==1{if r.Method!="GET"{method(w);return};st,err:=s.Journal.GetService(id);if err!=nil{bad(w,err);return};write(w,200,st);return};action:=parts[1];if action=="health"{if r.Method!="GET"{method(w);return};h,err:=s.Engine.Health(r.Context(),id);if err!=nil{bad(w,err);return};write(w,200,h);return};if r.Method!="POST"{method(w);return};if err:=s.requireMutationProof(r);err!=nil{http.Error(w,err.Error(),http.StatusForbidden);return};if action=="install"{var q struct{Request model.ServiceRequest `json:"request"`;ConfirmedPlanDigest string `json:"confirmed_plan_digest"`};if err:=decode(r,&q);err!=nil{bad(w,err);return};if q.Request.ServiceID!=id{bad(w,errors.New("service id mismatch"));return};op,err:=s.Engine.Install(r.Context(),q.Request,q.ConfirmedPlanDigest);if err!=nil{bad(w,err);return};write(w,200,op);return};switch action{case "start","stop","restart","upgrade","repair","backup","restore","uninstall":var q lifecycle.ActionRequest;if err:=decode(r,&q);err!=nil{bad(w,err);return};q.Action=action;op,err:=s.Engine.Action(r.Context(),id,q);if err!=nil{bad(w,err);return};write(w,200,op);default:http.NotFound(w,r)}}
func(s *Server)operationRoute(w http.ResponseWriter,r *http.Request){if r.Method!="GET"{method(w);return};id:=strings.Trim(strings.TrimPrefix(r.URL.Path,"/api/v1/operations/"),"/");op,err:=s.Journal.GetOperation(id);if err!=nil{bad(w,err);return};write(w,200,op)}
func(s *Server)requireMutationProof(r *http.Request)error{if s.AllowedOrigin!=""&&r.Header.Get("Origin")!=s.AllowedOrigin{return errors.New("origin rejected")};c,err:=r.Cookie("layersentry_csrf");if err!=nil||c.Value==""||r.Header.Get("X-CSRF-Token")!=c.Value{return errors.New("csrf rejected")};return nil}
func decode(r *http.Request,out any)error{limited:=io.LimitReader(r.Body,(1<<20)+1);dec:=json.NewDecoder(limited);dec.DisallowUnknownFields();if err:=dec.Decode(out);err!=nil{return err};var extra any;if err:=dec.Decode(&extra);err!=io.EOF{return errors.New("multiple JSON values are not allowed")};return nil}
func write(w http.ResponseWriter,status int,v any){w.Header().Set("Content-Type","application/json");w.WriteHeader(status);_ = json.NewEncoder(w).Encode(v)}
func bad(w http.ResponseWriter,err error){http.Error(w,fmt.Sprintf("request rejected: %s",err),http.StatusBadRequest)}
func serverErr(w http.ResponseWriter,_ error){http.Error(w,"internal error",http.StatusInternalServerError)}
func method(w http.ResponseWriter){http.Error(w,"method not allowed",http.StatusMethodNotAllowed)}
func randomHex(n int)string{b:=make([]byte,n);_,_ = rand.Read(b);return hex.EncodeToString(b)}
