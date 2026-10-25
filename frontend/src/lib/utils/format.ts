import { format, isThisYear, isToday } from 'date-fns';
import { enUS, ja } from 'date-fns/locale';

const PROVIDER_LABELS: Record<string, string> = {
    github: 'GitHub',
    google: 'Google',
};

export const formatAccountProvider = (provider?: string): null | string =>
    provider ? (PROVIDER_LABELS[provider] ?? provider) : null;

const DISPLAY_LABELS: Record<string, string> = {
    created: '作成済み',
    running: '実行中',
    waiting: '待機中',
    finished: '完了',
    failed: '失敗',
    pending: '未実行',
    stopped: '停止済み',
    cancelled: '中止',
    assistant: 'アシスタント',
    primary_agent: 'メインエージェント',
    pentester: '診断担当',
    adviser: 'アドバイザー',
    coder: 'コード担当',
    enricher: '情報補完',
    generator: '計画作成',
    installer: 'インストール担当',
    memorist: '記憶担当',
    refiner: '改善担当',
    reflector: '振り返り担当',
    reporter: 'レポート担当',
    searcher: '検索担当',
    summarizer: '要約担当',
    tool_call_fixer: 'ツール呼び出し修正',
};

export const formatName = (name?: string, localize = false): string => {
    if (localize && name && import.meta.env.VITE_UI_LANGUAGE !== 'en' && DISPLAY_LABELS[name])
        return DISPLAY_LABELS[name];
    return (name || '')
        .split('_')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
};

export const formatDate = (date: Date) => {
    if (isToday(date)) {
        return format(date, 'HH:mm:ss');
    }

    if (isThisYear(date)) {
        return format(date, import.meta.env.VITE_UI_LANGUAGE === 'en' ? 'HH:mm, d MMM' : 'M月d日 HH:mm', {
            locale: import.meta.env.VITE_UI_LANGUAGE === 'en' ? enUS : ja,
        });
    }

    return format(date, import.meta.env.VITE_UI_LANGUAGE === 'en' ? 'HH:mm, d MMM yyyy' : 'yyyy年M月d日 HH:mm', {
        locale: import.meta.env.VITE_UI_LANGUAGE === 'en' ? enUS : ja,
    });
};

export const formatTableDate = (date: Date) =>
    isThisYear(date)
        ? formatDate(date)
        : format(date, import.meta.env.VITE_UI_LANGUAGE === 'en' ? 'd MMM yyyy' : 'yyyy年M月d日', {
              locale: import.meta.env.VITE_UI_LANGUAGE === 'en' ? enUS : ja,
          });

export const formatNumber = (value: number): string => new Intl.NumberFormat('en-US').format(value);

export const formatTokenCount = (count: number): string => {
    if (count >= 1_000_000_000) {
        return `${(count / 1_000_000_000).toFixed(1)}B`;
    }

    if (count >= 1_000_000) {
        return `${(count / 1_000_000).toFixed(1)}M`;
    }

    if (count >= 1_000) {
        return `${(count / 1_000).toFixed(1)}K`;
    }

    return count.toString();
};

export const formatCost = (cost: number): string => {
    if (!cost) {
        return '$0';
    }

    if (cost >= 1) {
        return `$${cost.toFixed(2)}`;
    }

    if (cost >= 0.01) {
        return `$${cost.toFixed(3)}`;
    }

    return `$${cost.toFixed(4)}`;
};

export const formatDuration = (seconds: number): string => {
    if (seconds >= 3600) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        return `${hours}h ${minutes}m`;
    }

    if (seconds >= 60) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);

        return `${minutes}m ${remainingSeconds}s`;
    }

    if (seconds >= 1) {
        return `${seconds.toFixed(1)}s`;
    }

    return `${(seconds * 1000).toFixed(0)}ms`;
};
