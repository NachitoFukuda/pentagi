import { ProviderType } from '@/graphql/types';

export interface Provider {
    backend?: 'codex-cli';
    name: string;
    type: ProviderType;
}

export const getProviderDisplayName = (provider: Provider): string => {
    if (provider.backend === 'codex-cli') {
        return 'Codex CLI';
    }

    return provider.name;
};

// Detect the actual authenticated bridge catalogue, rather than labelling every
// custom/API-compatible provider as Codex based on its generic type.
export const hasCodexCliBackend = (
    settings?: null | {
        default?: { custom?: null | { agents: { simple: { model: string } } } };
        models?: { custom?: null | readonly { name: string }[] };
    },
): boolean => {
    const model = settings?.default?.custom?.agents.simple.model;
    const catalogue = settings?.models?.custom ?? [];
    if (!catalogue.some((item) => item.name === 'codex-local')) return false;
    // Empty per-agent model means it inherits LLM_SERVER_MODEL. The CLI bridge
    // exposes exactly one alias, so this inherited configuration is unambiguous.
    return model === 'codex-local' || (model === '' && catalogue.every((item) => item.name === 'codex-local'));
};

export const isProviderValid = (provider: Provider, providers: Provider[]): boolean => {
    return providers.some((p) => p.name === provider.name && p.type === provider.type);
};

export const isProviderMissing = (provider: Provider, providers: Provider[]): boolean => {
    return providers.length > 0 && !isProviderValid(provider, providers);
};

export const findProviderByName = (providerName: string, providers: Provider[]): Provider | undefined => {
    return providers.find((provider) => provider.name === providerName);
};

export const sortProviders = (providers: Provider[]): Provider[] => {
    return [...providers].sort((a, b) => a.name.localeCompare(b.name));
};
