//go:build codexonly

package ollama

import (
	"fmt"
	"pentagi/pkg/config"
	"pentagi/pkg/providers/pconfig"
	"pentagi/pkg/providers/provider"
)

func BuildProviderConfig(_ *config.Config, _ []byte) (*pconfig.ProviderConfig, error) {
	return nil, fmt.Errorf("Ollama is excluded from the Codex-only build")
}
func DefaultProviderConfig(_ *config.Config) (*pconfig.ProviderConfig, error) {
	return nil, fmt.Errorf("Ollama is excluded from the Codex-only build")
}
func New(_ *config.Config, _ provider.ProviderName, _ *pconfig.ProviderConfig) (provider.Provider, error) {
	return nil, fmt.Errorf("Ollama is excluded from the Codex-only build")
}
