import { describe, expect, it } from 'vitest';

import { ProviderType } from '@/graphql/types';

import { getProviderDisplayName, hasCodexCliBackend, isProviderValid } from './provider';

describe('Codex CLI provider identity', () => {
    it('requires both the configured alias and the bridge model catalogue', () => {
        expect(hasCodexCliBackend()).toBe(false);
        expect(hasCodexCliBackend({ default: { custom: { agents: { simple: { model: 'codex-local' } } } } })).toBe(
            false,
        );
        expect(
            hasCodexCliBackend({
                default: { custom: { agents: { simple: { model: 'other' } } } },
                models: { custom: [{ name: 'codex-local' }] },
            }),
        ).toBe(false);
        expect(
            hasCodexCliBackend({
                default: { custom: { agents: { simple: { model: 'codex-local' } } } },
                models: { custom: [{ name: 'codex-local' }] },
            }),
        ).toBe(true);
    });
    it('recognizes an inherited model only with the exclusive CLI catalogue', () => {
        const defaults = { custom: { agents: { simple: { model: '' } } } };
        expect(hasCodexCliBackend({ default: defaults, models: { custom: [{ name: 'codex-local' }] } })).toBe(true);
        expect(
            hasCodexCliBackend({ default: defaults, models: { custom: [{ name: 'codex-local' }, { name: 'other' }] } }),
        ).toBe(false);
    });
    it('changes the display label while keeping the provider identifier intact', () => {
        const provider = { backend: 'codex-cli' as const, name: 'custom', type: ProviderType.Custom };
        expect(getProviderDisplayName(provider)).toBe('Codex CLI');
        expect(provider.name).toBe('custom');
        expect(isProviderValid(provider, [{ name: 'custom', type: ProviderType.Custom }])).toBe(true);
        expect(getProviderDisplayName({ name: 'My API provider', type: ProviderType.Custom })).toBe('My API provider');
    });
});
