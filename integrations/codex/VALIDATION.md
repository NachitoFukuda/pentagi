# 検証記録 — 2026-10-24

対象: 上流 `cffed9485aa1cca70762cd08a57ac62a80406258` を基にした、このフォークの変更。
環境: macOS ARM64、Go 1.26.10、Node 26.8.1、pnpm 11.8.0、Codex CLI 0.163.0-alpha.10.2（ChatGPTログイン）。

## 修正と切り分け

- x/net 0.58.0 → 0.60.0、x/crypto 0.55.0 → 0.57.0、jsonparser 1.1.1 → 1.1.2、compress 1.18.3 → 1.18.7。
- OTLP trace exporterを1.45.0へ統一。x/mod等も整合する修正版へ更新。
- Axios 1.20.0、Vite 8.3.5、Zod 4.6.7、Vitest 5.0.5、GraphQLコード生成と間接依存を更新。主要バージョンを維持できるものは系列ごとにoverride。
- `pnpm audit` 最終結果: 依存1,133件、info/low/moderate/high/criticalの全て0件。開発用も含む。この結果はnpmレジストリの既知告知との照合であり、無害性の証明ではない。
- 実行用 `-tags codexonly` バイナリは、使わない上流Ollamaクライアントを除外。依存パッケージ一覧にも `github.com/ollama/ollama`、langchaingoのOllama実装は含まれない。
- govulncheck v1.9.0の最終バイナリ検査: package/symbolの一致0件。モジュール名だけの一致としてGO-2026-5932が1件残る。
- GO-2026-5932は非推奨の `golang.org/x/crypto/openpgp` に関する告知。今回の実行バイナリはこのパッケージを含まない。bcrypt/ssh等を使うためモジュール自体は残る。モジュール一致を「脆弱な関数が使われている」と解釈していない。
- 上流の全機能を含む通常ビルドについて、Ollama関連の告知を解消済みとは主張しない。今回の対象はCodex用ビルド。

最初のsourceモードによるコールグラフ解析は、このMacのメモリー負荷が高いため中断し、完成した実行バイナリの検査に切り替えた。
バイナリ検査と、対象パッケージが含まれないことの確認を組み合わせている。未知の脆弱性・OSイメージ全体・全ての実行経路の安全証明ではない。

## 自動確認

- ブリッジ7テスト: 不正認証、同時実行制限、通常応答/SSE、未提供ツール拒否、引数JSON、画像/モデル差替拒否、公開アドレスへのbind拒否等。
- Go: config、server/update、observability、providers/custom、providers/embeddingsを確認。cmd/pentagiはコンパイル確認（既存テストなし）。
- Codex用タグでcustomプロバイダーとcmd/pentagiのコンパイルも確認。
- `go mod verify`: 成功。
- フロントエンド: 本番ビルド成功。全2,539テスト中2,538件成功、1件は負荷中の5秒タイムアウト。そのファイルを単独・1ワーカー・30秒上限で再実行し4件全て成功。機能エラーを黙って除外していない。
- `git diff --check`: 成功。

## 実動作

1. 専用Colima VMを新規作成。ホストのフォルダー共有とSSHエージェント共有なし。
2. ソースからローカルビルドしたバックエンドとフロントエンドを、固定digestのDebianイメージへ格納。
3. 本体をVM内UID 10001、read-only root、cap_drop ALL、no-new-privilegesで起動。
4. 初期管理者パスワードを待受開始前にランダム値へ置換し、その値でログインHTTP 200を確認。
5. ブラウザーでログイン画面のレンダリング、APIでcustom / codex-localプロバイダーの認識を確認。
6. Mac上の認証済み公式Codex CLIから `PENTAGI_CODEX_OK` 応答を取得。APIキーへの切替なし。
7. 実際のPentAGIフローを作成。Codexがmaintenance/terminal等のfunction callを返し、ワーカーで `printf PENTAGI_WORKER_OK` を実行。
8. DBのterminalツール結果に `PENTAGI_WORKER_OK` と `[exit code: 0]` が保存され、taskがfinishedになったことを確認。
9. 上流の通常動作に従ってフローは報告後waitingになったため、APIのfinish操作を行い、再取得でflow=finishedを確認。ワーカーも削除された。

## 通信・権限の確認

- 本体はVMループバック以外へのOUTPUTを拒否。予約済みテスト用IPへの接続を試し、拒否ルールのカウンター増加と接続失敗を確認。
- 実フローのワーカーは `pentagi-workers` にのみ接続。Gatewayなし、ルーティングテーブルにdefault routeなし。
- ワーカーのmountは専用 `/work` ボリュームのみ。Dockerソケット共有なし、privileged=false。
- 同じ内部ネットワーク上の検証コンテナからVMホストのブリッジ用ポートと予約済み外部IPへの接続が失敗することを確認。
- 外部送信先を設定した状態でも、明示的なreporting opt-inがなければLangfuse/OTelクライアントを作らず、更新クライアントも生成しないことをテスト。
- これはパケットを全て復号・監査した結果ではなく、設定・コード上の遮断と接続試験による検証。推論のためのOpenAIとの通信はMac上のCodex CLIが行う。

秘密値と生の実行証拠はローカルの追跡対象外 `.state` に保存。ChatGPT認証ファイルと生成した管理者・DB・ブリッジの秘密値はコミットに含めない。
