const PoetrySearch = {
    search: async () => {
        const keyword = document.getElementById('poetryKeyword').value.trim();

        if (!keyword) {
            alert('请输入关键词');
            return;
        }

        // 2. 显示加载中
        document.getElementById('poetryLoading').style.display = 'block';
        document.getElementById('poetryResult').style.display = 'none';

        try {
            // 3. 调用 API
            const response = await fetch('/api/poetry/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    keyword: keyword
                })
            });

            const result = await response.json();

            if (result.success) {
                PoetrySearch.render(result.data);
            } else {
                alert(result.message || '未找到相关诗词');
            }

        } catch (error) {
            console.error('Error:', error);
            alert('系统繁忙，请稍后再试');
        } finally {
            document.getElementById('poetryLoading').style.display = 'none';
        }
    },

    render: (data) => {
        document.getElementById('poetryResult').style.display = 'block';
        
        document.getElementById('pTitle').innerText = data.title;
        document.getElementById('pAuthor').innerText = data.author; // 已经包含 [唐]
        
        // 处理原文，增加 tooltip
        // data.content 可能是纯文本，换行符 \n
        // data.annotations 是数组 [{word, note}]
        let contentHtml = data.content.replace(/\n/g, '<br>');
        
        if (data.annotations && Array.isArray(data.annotations)) {
            // 简单处理：遍历 annotations，把 contentHtml 里的 word 替换带 tooltip 的 span
            data.annotations.forEach(anno => {
                const word = anno.word;
                const note = anno.note;
                // 使用正则替换，加上 class 和 data-bs-toggle
                // 这是一个简化的替换，如果同一个字出现多次可能会全被替换
                try {
                    const regex = new RegExp(word, 'g');
                    contentHtml = contentHtml.replace(regex, `<span class="poetry-annotation" data-bs-toggle="tooltip" title="${note}">${word}</span>`);
                } catch(e) {
                    console.warn('Annotation regex error', e);
                }
            });
        }
        
        document.getElementById('pContent').innerHTML = contentHtml;
        document.getElementById('pTranslation').innerText = data.translation;
        document.getElementById('pAppreciation').innerText = data.appreciation;

        // 激活 Tooltip
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
};

// 支持回车搜索
document.getElementById('poetryKeyword').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        PoetrySearch.search();
    }
});
