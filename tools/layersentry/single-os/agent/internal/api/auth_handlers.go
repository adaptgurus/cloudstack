package api

import "net/http"

func (s *Server) bootstrapLimited(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost { method(w); return }
	if ok, retry := allowAuthAttempt("bootstrap", r.RemoteAddr); !ok { authRateLimited(w, retry); return }
	var q struct{ Token string `json:"token"`; Username string `json:"username"`; Password string `json:"password"` }
	if err := decode(r, &q); err != nil { recordAuthFailure("bootstrap", r.RemoteAddr); bad(w, err); return }
	err := s.Auth.Bootstrap(s.BootstrapFile, q.Token, q.Username, q.Password)
	q.Password = ""; q.Token = ""
	if err != nil { recordAuthFailure("bootstrap", r.RemoteAddr); http.Error(w, "bootstrap rejected", http.StatusBadRequest); return }
	recordAuthSuccess("bootstrap", r.RemoteAddr)
	write(w, http.StatusCreated, map[string]string{"status":"administrator-created"})
}

func (s *Server) loginLimited(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost { method(w); return }
	if ok, retry := allowAuthAttempt("login", r.RemoteAddr); !ok { authRateLimited(w, retry); return }
	var q struct{ Username string `json:"username"`; Password string `json:"password"` }
	if err := decode(r, &q); err != nil { recordAuthFailure("login", r.RemoteAddr); bad(w, err); return }
	token, exp, err := s.Auth.Login(q.Username, q.Password); q.Password = ""
	if err != nil { recordAuthFailure("login", r.RemoteAddr); http.Error(w, "invalid credentials", http.StatusUnauthorized); return }
	recordAuthSuccess("login", r.RemoteAddr)
	csrf := randomHex(24)
	http.SetCookie(w, &http.Cookie{Name:"layersentry_session", Value:token, Path:"/", Secure:true, HttpOnly:true, SameSite:http.SameSiteStrictMode, Expires:exp})
	http.SetCookie(w, &http.Cookie{Name:"layersentry_csrf", Value:csrf, Path:"/", Secure:true, HttpOnly:false, SameSite:http.SameSiteStrictMode, Expires:exp})
	write(w, http.StatusOK, map[string]string{"status":"authenticated", "csrf_token":csrf})
}
