//go:build codexonly

package embeddings

import (
	"fmt"
	"github.com/vxcontrol/langchaingo/embeddings"
	"net/http"
	"pentagi/pkg/config"
)

func newOllama(_ *config.Config, _ *http.Client) (embeddings.Embedder, error) {
	return nil, fmt.Errorf("Ollama embeddings are excluded from the Codex-only build")
}
