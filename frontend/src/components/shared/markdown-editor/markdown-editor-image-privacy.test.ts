import { Editor } from '@tiptap/core';
import { beforeAll, describe, expect, it } from 'vitest';

import { createMarkdownExtensions } from './markdown-editor-extensions';
import { setupEditorJsdom } from './markdown-editor-test-setup';

beforeAll(setupEditorJsdom);

describe('Markdown image privacy in the mounted editor', () => {
    it.each(['https://attacker.invalid/pixel?value=DUMMY', '/api/v1/info?value=DUMMY'])(
        'keeps %s as document data without mounting a network-capable image',
        (src) => {
            const element = document.createElement('div');
            document.body.append(element);
            const content = `![diagnostic](${src})`;
            const editor = new Editor({
                element,
                content,
                contentType: 'markdown',
                extensions: createMarkdownExtensions(),
            });

            try {
                expect(editor.view.dom.querySelector('img, [src], [srcset]')).toBeNull();
                expect(editor.view.dom.textContent).toContain('diagnostic');
                expect(editor.getMarkdown()).toContain(content);
                editor.commands.setContent(`![updated](${src})`, { contentType: 'markdown' });
                expect(editor.view.dom.textContent).toContain('updated');
                expect(editor.view.dom.querySelector('img, [src], [srcset]')).toBeNull();
                expect(editor.getMarkdown()).toContain(`![updated](${src})`);
            } finally {
                editor.destroy();
                element.remove();
            }
        },
    );
});
