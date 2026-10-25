//go:build !codexonly

package embeddings

import (
	"fmt"
	"github.com/vxcontrol/langchaingo/embeddings"
	"github.com/vxcontrol/langchaingo/llms/ollama"
	"net/http"
	"pentagi/pkg/config"
	"pentagi/pkg/observability/langfuse"
)

func newOllama(cfg *config.Config, httpClient *http.Client) (embeddings.Embedder, error) {
	model, provider := cfg.EmbeddingModel, "ollama"

	var opts []ollama.Option
	metadata := langfuse.Metadata{
		"strip_new_lines": cfg.EmbeddingStripNewLines,
		"batch_size":      cfg.EmbeddingBatchSize,
	}
	serverURL, key := embeddingServer(cfg.EmbeddingURL, "", cfg.OllamaServerURL, cfg.OllamaServerAPIKey, "")
	if serverURL != "" {
		opts = append(opts, ollama.WithServerURL(serverURL))
		metadata["url"] = serverURL
	}
	if key != "" {
		opts = append(opts, ollama.WithAPIKey(key))
	}
	if cfg.EmbeddingModel != "" {
		opts = append(opts, ollama.WithModel(cfg.EmbeddingModel))
	}
	if httpClient != nil {
		opts = append(opts, ollama.WithHTTPClient(httpClient))
	}

	client, err := ollama.New(opts...)
	if err != nil {
		return nil, fmt.Errorf("failed to create ollama client: %w", err)
	}

	eopts := []embeddings.Option{
		embeddings.WithStripNewLines(cfg.EmbeddingStripNewLines),
		embeddings.WithBatchSize(cfg.EmbeddingBatchSize),
	}

	e, err := embeddings.NewEmbedder(client, eopts...)
	if err != nil {
		return nil, fmt.Errorf("failed to create embedder: %w", err)
	}

	return &wrapper{
		model:    model,
		provider: provider,
		metadata: metadata,
		Embedder: e,
	}, nil
}
