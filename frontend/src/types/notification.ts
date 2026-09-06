export type OrderNotification = {
  order_id: string; reference: string; client_name: string; category: string; title: string; message: string;
  status: string; is_demo: boolean; updated_at: string; fingerprint: string; is_read: boolean;
};
export type NotificationList = { items: OrderNotification[]; total: number; unread_count: number; page: number; page_size: number };
