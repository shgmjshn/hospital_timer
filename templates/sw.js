// 確定呼出（イベントB）をロック画面などへ表示するサービスワーカー。
// 画面を閉じていても届くのはこの経路だけなので、通知はタップされるまで残す。

self.addEventListener("push", (event) => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(
    self.registration.showNotification(data.title || "診察のご案内", {
      body: data.body || "",
      tag: data.tag || "clinic-call",
      requireInteraction: true,
      data: {url: data.url || "/"},
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
