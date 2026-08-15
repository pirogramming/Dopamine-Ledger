const crewEl = document.getElementById('crew-data');
const crewId = crewEl.dataset.crewId;

// 현재 URL의 정렬값 유지 (?sort=name 등)
const currentSort =
    new URLSearchParams(window.location.search).get('sort') || 'contribution';

async function refreshMembers() {
    try {
        const res = await fetch(`/crew/${crewId}/members/?sort=${currentSort}`);
        if (!res.ok) return;   // 에러면 조용히 넘어감 (다음 주기에 재시도)
        const data = await res.json();

        // 인원수 · 상태 갱신
        document.getElementById('member-count').textContent = data.member_count;
        const statusEl = document.getElementById('crew-status');
        if (statusEl) statusEl.textContent = data.status;

        // 멤버 목록 다시 그리기 (crew_detail.html의 .member-item 구조와 동일하게)
        const list = document.getElementById('member-list');
        list.innerHTML = '';

        data.members.forEach(m => {
            const row = document.createElement('a');
            row.className = 'member-item' + (m.is_top ? ' member-item--top' : '');
            row.href = `/crew/${crewId}/member/${m.id}/`;

            const avatar = document.createElement('div');
            avatar.className = 'member-avatar';

            const avatarImg = document.createElement('img');
            avatarImg.className = 'profile-character-img';
            avatarImg.src = '/static/' + m.profile_character_url;
            avatar.appendChild(avatarImg);

            // 왼쪽: 이름 + 피드문구
            const main = document.createElement('div');
            main.className = 'member-main';

            const nameDiv = document.createElement('div');
            nameDiv.className = 'member-name';
            nameDiv.textContent = m.name;
            if (m.is_owner) {
                const crown = document.createElement('span');
                crown.className = 'member-crown';
                crown.textContent = ' 👑';
                nameDiv.appendChild(crown);
            }

            const feed = document.createElement('div');
            feed.className = 'member-feed';
            feed.textContent = m.feed_text;

            main.appendChild(nameDiv);
            main.appendChild(feed);

            // 오른쪽: 퍼센트 + 누적시간
            const stat = document.createElement('div');
            stat.className = 'member-stat';

            const pct = document.createElement('div');
            pct.className = 'member-pct' + (m.is_top ? ' member-pct--top' : '');
            pct.textContent = m.contribution_pct + '%';

            const time = document.createElement('div');
            time.className = 'member-time';
            time.textContent = m.contribution_hm;

            stat.appendChild(pct);
            stat.appendChild(time);

            row.appendChild(avatar);
            row.appendChild(main);
            row.appendChild(stat);
            list.appendChild(row);
        });
    } catch (e) {
        // 네트워크 오류 등은 무시하고 다음 주기에 재시도
    }
}

// 10초마다 갱신
setInterval(refreshMembers, 10000);