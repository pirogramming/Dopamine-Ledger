const crewEl = document.getElementById('crew-data');
const crewId = crewEl.dataset.crewId;
const ownerLabel = "👑 (크루장)";

async function refreshMembers() {
    try {
        const res = await fetch(`/crew/${crewId}/members/`);
        if (!res.ok) return;   // 에러면 조용히 넘어감 (다음 주기에 재시도)
        const data = await res.json();

        // 인원수 · 상태 갱신
        document.getElementById('member-count').textContent = data.member_count;
        document.getElementById('crew-status').textContent = data.status;

        // 멤버 목록 다시 그리기
        const list = document.getElementById('member-list');
        list.innerHTML = '';
        data.members.forEach(m => {
            const row = document.createElement('a');
            row.className = 'member-row';
            row.href = `/crew/${crewId}/member/${m.id}/`;

        const avatar = document.createElement('img');
        avatar.className = 'member-avatar';
        avatar.src = '/static/' + m.character;
        avatar.alt = '캐릭터';

        const nameDiv = document.createElement('div');
        nameDiv.className = 'member-name';
        nameDiv.textContent = m.name;
        if (m.is_owner) {
            const crown = document.createElement('span');
            crown.className = 'member-crown';
            crown.textContent = ' 👑 크루장';
            nameDiv.appendChild(crown);
        }

        row.appendChild(avatar);
        row.appendChild(nameDiv);
        list.appendChild(row);
    });
    } catch (e) {
        // 네트워크 오류 등은 무시하고 다음 주기에 재시도
    }
}

// 10초마다 갱신
setInterval(refreshMembers, 10000);