package lifecycle

import (
	"context"
	"errors"
	"fmt"

	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/packageutil"
)

func verifyTransactionalProvenance(ctx context.Context, runner executor.Runner, plan model.Plan) error {
	if runner == nil {
		return errors.New("repository provenance executor unavailable")
	}
	dnf := packageutil.DNF{Runner: runner}
	if plan.RepositoryID == "" || plan.RepositoryDigest == "" {
		return errors.New("provider repository provenance missing from immutable plan")
	}
	observed, err := dnf.RepositoryDigest(ctx, plan.RepositoryID)
	if err != nil {
		return fmt.Errorf("revalidate provider repository %s: %w", plan.RepositoryID, err)
	}
	if observed != plan.RepositoryDigest {
		return fmt.Errorf("provider repository %s drifted after plan confirmation", plan.RepositoryID)
	}
	for _, pin := range plan.PlatformPackages {
		if pin.Package == "" || pin.ResolvedVersion == "" || pin.RepositoryID == "" || pin.RepositoryDigest == "" {
			return errors.New("platform package provenance is incomplete")
		}
		observed, err = dnf.RepositoryDigest(ctx, pin.RepositoryID)
		if err != nil {
			return fmt.Errorf("revalidate platform repository %s: %w", pin.RepositoryID, err)
		}
		if observed != pin.RepositoryDigest {
			return fmt.Errorf("platform repository %s drifted after plan confirmation", pin.RepositoryID)
		}
	}
	return nil
}
