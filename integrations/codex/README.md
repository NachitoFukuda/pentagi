# Codex CLI版 PentAGI（macOS / Apple Silicon）

ChatGPTにログイン済みの公式Codex CLIを、PentAGIのローカルLLMバックエンドとして使います。
OpenAI APIキーは不要です。推論用の会話・検査結果はCodexを通してOpenAIへ送られます。
ChatGPTの認証ファイルを読み出したり、仮想マシンにコピーしたりする構成ではありません。

## 分離と通信

- Colima専用プロファイル `pentagi-secure`。Macのホームフォルダー共有、SSHエージェント共有なし。
- PentAGI本体はVM内のコンテナでUID 10001として実行。読み取り専用ルート、全capabilityを除去。
- PentAGIの通信はVMのループバックのみ許可。更新報告、Langfuse、OpenTelemetry、外部検索、外部embeddingを無効化。
- ワーカーは `pentagi-workers` 内部ネットワーク。インターネット経路、VMホストへの接続、Dockerソケットの共有なし。
- PentAGI本体だけが専用VMのDockerソケットを操作します。この権限は依然としてVM内では強い権限です。
- Mac上のブリッジは `127.0.0.1:18765` のみ。ランダムなBearerトークンで保護し、SSH reverse tunnelでVMに接続。
- Codexは空の作業ディレクトリ、read-only、ユーザー設定・MCP・プラグイン・フック・メモリー・シェル・ブラウザー等を無効にして呼びます。
- Codexのfunction callはJSONデータとしてPentAGIに返し、端末操作はPentAGIワーカーで実行します。
- この構成は隔離検証用です。実環境の診断には、対象を決めて必要な通信だけを許可する追加設定が必要です。

## 準備とビルド

必要: macOS ARM64、Go 1.26.10以降、Node.js、pnpm 11.8.0、Docker CLI、docker-compose、Colima、公式Codex CLI。
`codex login status` がChatGPTログインを示すことを確認してください。

```sh
cd frontend
pnpm install --frozen-lockfile --ignore-scripts
pnpm run build
cd ../backend
mkdir -p ../.state
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -tags codexonly -trimpath -o ../.state/pentagi-linux-arm64 ./cmd/pentagi
cd ..
PENTAGI_CODEX_MODEL=gpt-6.1-sol integrations/codex/start.sh
```

`codexonly` は不要なOllamaクライアントを実行バイナリから除外します。通常ビルドには従来のOllama対応が残ります。
このフォークの標準起動手順は上記です。上流のインストーラーや既定コンテナイメージは使いません。
モデル名はログインで利用できるものを `PENTAGI_CODEX_MODEL` で指定してください。
Goバイナリの配置先 `.state` がなければ `mkdir -p .state` を先に実行してください。

画面: http://127.0.0.1:18443
ログイン情報: `.state/login.txt`（権限600）。初回にランダムな管理者・DB・ブリッジの秘密値を生成します。
これらをGitHubに追加しないでください。`.state` は追跡対象外です。
初期の既知パスワードは、HTTP待受開始前にランダムな値へ置き換えます。既存の変更済みパスワードは上書きしません。

停止: `integrations/codex/stop.sh`。データボリュームは保持します。
VMも止める場合は `colima stop pentagi-secure` を使います。
VM再起動後は必ず `start.sh` を使って通信制限とトンネルを再設定してください。

## 互換性と制限

テキスト会話、JSON応答、function tool calls、tool results、ストリーミング形式に対応します。
SSE応答はCodexの最終出力を受け取ってから返すため、トークン単位の逐次表示ではありません。
画像入力は明示的に拒否します。embeddingと画像ベースのブラウザー検査は、この構成では使いません。
1件ずつ推論し、同時要求には429を返します。CLIでログアウトした場合は再ログインが必要です。
ChatGPTの利用上限・利用可能なモデルに従います。APIキー課金へ自動で切り替えません。

## 検証

```sh
python3 -m unittest discover -s integrations/codex -p 'test_*.py'
cd frontend && pnpm audit && pnpm test && pnpm run build
cd ../backend
go test ./pkg/config ./pkg/server/update ./pkg/observability ./pkg/providers/custom ./pkg/providers/embeddings ./cmd/pentagi
go test -tags codexonly ./pkg/providers/custom ./cmd/pentagi
```

今回の検証記録は [VALIDATION.md](VALIDATION.md) を参照してください。
