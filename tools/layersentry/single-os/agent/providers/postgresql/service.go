package postgresql

import (
 "context"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

func(p *Provider)Start(ctx context.Context,_ model.Operation,st model.ServiceState)error{_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","enable","--now","postgresql-"+st.ReleaseLine+".service");return err}
func(p *Provider)Stop(ctx context.Context,_ model.Operation,st model.ServiceState)error{_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","stop","postgresql-"+st.ReleaseLine+".service");return err}
func(p *Provider)Restart(ctx context.Context,_ model.Operation,st model.ServiceState)error{_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","restart","postgresql-"+st.ReleaseLine+".service");return err}
