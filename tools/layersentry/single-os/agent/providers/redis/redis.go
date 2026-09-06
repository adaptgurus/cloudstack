// Package redis is retained as a source-compatibility shim for callers that
// imported the earlier Redis provider package. The implementation now delegates
// to providers/keyvalue, which persists only an ACL SHA-256 password verifier
// and never writes the plaintext administrator password into Redis config.
package redis

import (
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/backupcrypto"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/executor"
	"github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/providers/keyvalue"
)

type SecretGetter = keyvalue.SecretGetter
type Provider = keyvalue.Provider

func New(r executor.Runner, s SecretGetter, b *backupcrypto.Keyring) *Provider {
	return keyvalue.Redis(r, s, b)
}
