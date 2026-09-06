package nginx

import (
 "context"
 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

func(p *Provider)Start(ctx context.Context,_ model.Operation,_ model.ServiceState)error{_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","start","nginx.service");return err}
func(p *Provider)Stop(ctx context.Context,_ model.Operation,_ model.ServiceState)error{_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","stop","nginx.service");return err}
func(p *Provider)Restart(ctx context.Context,_ model.Operation,_ model.ServiceState)error{_,err:=p.Runner.Run(ctx,"/usr/bin/systemctl","restart","nginx.service");return err}
