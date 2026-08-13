from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from budget.models import Activity

User = get_user_model()


class RateEditActivityCRUDTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="crud@example.com",
            email="crud@example.com",
            password="test-pass-1234",
            nickname="크루드테스트",
        )
        self.client.force_login(self.user)
        self.url = reverse("rate-edit")
        # 온보딩 기본 3개 흉내
        for name in ["독서", "운동", "공부"]:
            Activity.objects.create(
                users=self.user, activity_type=name,
                rate=Decimal("0.5"), is_active=True,
            )

    def _active(self):
        return Activity.objects.filter(users=self.user, is_active=True)

    # 1) 추가
    def test_add_activity(self):
        self.client.post(self.url, {
            "action": "add", "new_name": "산책", "new_minutes": "20",
        })
        self.assertTrue(self._active().filter(activity_type="산책").exists())
        walk = self._active().get(activity_type="산책")
        self.assertEqual(walk.rate, Decimal("0.3333"))   # 20/60=0.3333(4자리)

    # 2) 상한 6개
    def test_cannot_exceed_six(self):
        for name in ["산책", "요리", "명상"]:   # 3+3=6
            self.client.post(self.url, {
                "action": "add", "new_name": name, "new_minutes": "20",
            })
        self.assertEqual(self._active().count(), 6)
        # 7개째 시도 → 막힘
        self.client.post(self.url, {
            "action": "add", "new_name": "일곱번째", "new_minutes": "20",
        })
        self.assertEqual(self._active().count(), 6)
        self.assertFalse(self._active().filter(activity_type="일곱번째").exists())

    # 3) 삭제 = 비활성화 (레코드 보존)
    def test_delete_is_soft(self):
        book = self._active().get(activity_type="독서")
        self.client.post(self.url, {
            "action": "delete", "activity_id": book.id,
        })
        book.refresh_from_db()
        self.assertFalse(book.is_active)                        # 비활성
        self.assertTrue(Activity.objects.filter(id=book.id).exists())  # 행 보존

    # 4) 재활성화 (같은 이름 다시 추가 → 새로 안 만들고 되살림)
    def test_re_add_revives(self):
        book = self._active().get(activity_type="독서")
        book_id = book.id
        self.client.post(self.url, {
            "action": "delete", "activity_id": book_id,
        })
        self.client.post(self.url, {
            "action": "add", "new_name": "독서", "new_minutes": "30",
        })
        books = Activity.objects.filter(users=self.user, activity_type="독서")
        self.assertEqual(books.count(), 1)          # 중복 생성 안 됨
        revived = books.first()
        self.assertEqual(revived.id, book_id)       # 같은 행 재사용
        self.assertTrue(revived.is_active)
        self.assertEqual(revived.rate, Decimal("0.5"))  # 30/60=0.5

    # 5) 최소 1개 방어
    def test_cannot_delete_last(self):
        for name in ["운동", "공부"]:               # 2개 지우고 1개만
            act = self._active().get(activity_type=name)
            self.client.post(self.url, {
                "action": "delete", "activity_id": act.id,
            })
        self.assertEqual(self._active().count(), 1)
        last = self._active().first()
        self.client.post(self.url, {
            "action": "delete", "activity_id": last.id,
        })
        self.assertEqual(self._active().count(), 1)  # 안 지워짐

    # 6) 활성 동명 중복 방어
    def test_no_duplicate_active(self):
        self.client.post(self.url, {
            "action": "add", "new_name": "독서", "new_minutes": "20",
        })
        self.assertEqual(self._active().filter(activity_type="독서").count(), 1)