import { Terminal } from 'lucide-react';

/** Describes the configured backend, not a live availability/billing indicator. */
export function CodexEngineNotice() {
    return (
        <div
            className="bg-muted/30 flex gap-3 rounded-lg border p-4 text-sm"
            role="note"
        >
            <Terminal className="mt-0.5 size-4 shrink-0" />
            <div className="flex min-w-0 flex-col gap-1">
                <p className="font-medium">Inference engine: Codex CLI</p>
                <p className="text-muted-foreground">
                    Uses this Mac's Codex CLI with ChatGPT sign-in. No OpenAI API key is required.
                </p>
                <p className="text-muted-foreground text-xs">
                    GPT inference runs through Codex CLI. The local connector only relays messages.
                </p>
            </div>
        </div>
    );
}
