const PoetrySearch = {
    // 防抖定时器
    _debounceTimer: null,

    search: async (title) => {
        // 支持传入标题直接搜索
        const keyword = title || document.getElementById('poetryKeyword').value.trim();

        if (!keyword) {
            alert('请输入关键词');
            return;
        }

        // 如果是点击候选项触发的，把标题回填到输入框
        if (title) {
            document.getElementById('poetryKeyword').value = title;
        }

        // 关闭候选下拉
        PoetrySearch.hideSuggest();

        // 显示加载中
        document.getElementById('poetryLoading').style.display = 'block';
        document.getElementById('poetryResult').style.display = 'none';

        try {
            const result = await TaskPoller.submitAndPoll('/api/poetry/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keyword: keyword })
            });

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

    // 输入联想：防抖查询候选列表
    onInput: (e) => {
        clearTimeout(PoetrySearch._debounceTimer);
        const q = e.target.value.trim();

        if (q.length < 1) {
            PoetrySearch.hideSuggest();
            return;
        }

        PoetrySearch._debounceTimer = setTimeout(async () => {
            try {
                const res = await fetch(`/api/poetry/suggest?q=${encodeURIComponent(q)}`);
                const json = await res.json();
                PoetrySearch.renderSuggest(json.data || []);
            } catch (err) {
                console.warn('联想查询失败', err);
            }
        }, 250);
    },

    // 渲染候选下拉
    renderSuggest: (items) => {
        const dropdown = document.getElementById('suggestDropdown');

        if (!items.length) {
            dropdown.classList.remove('show');
            dropdown.innerHTML = '';
            return;
        }

        dropdown.innerHTML = items.map(item =>
            `<div class="suggest-item" onclick="PoetrySearch.search('${item.title.replace(/'/g, "\\'")}')">
                <span class="title">${item.title}</span>
                <span class="author">${item.author}</span>
            </div>`
        ).join('');

        dropdown.classList.add('show');
    },

    hideSuggest: () => {
        const dropdown = document.getElementById('suggestDropdown');
        dropdown.classList.remove('show');
        dropdown.innerHTML = '';
    },

    render: (data) => {
        document.getElementById('poetryResult').style.display = 'block';
        
        document.getElementById('pTitle').innerText = data.title;
        document.getElementById('pAuthor').innerText = data.author;
        
        // 处理原文，增加 tooltip
        let contentHtml = data.content.replace(/\n/g, '<br>');
        
        if (data.annotations && Array.isArray(data.annotations)) {
            data.annotations.forEach(anno => {
                const word = anno.word;
                const note = anno.note;
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

// 绑定事件
const poetryInput = document.getElementById('poetryKeyword');

// 回车搜索
poetryInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        PoetrySearch.search();
    }
});

// 输入联想
poetryInput.addEventListener('input', PoetrySearch.onInput);

// 点击页面其他区域关闭下拉
document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-wrapper')) {
        PoetrySearch.hideSuggest();
    }
});
