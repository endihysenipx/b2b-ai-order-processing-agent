import type { Client } from "./client";

export interface OrderItem {
  id: string;
  article_number: string | null;
  model_number: string | null;
  quantity: number | null;
  unit_price: string | null;
  total_price: string | null;
  currency: string | null;
}

export interface OrderListItem {
  id: string;
  ticket_number: string | null;
  commission_number: string | null;
  customer_name: string | null;
  delivery_week: string | null;
  status: string;
  created_at: string;
  client: Client;
}

export interface OrderListResponse {
  items: OrderListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface OrderDetail extends OrderListItem {
  customer_number: string | null;
  commission_name: string | null;
  store_address: string | null;
  delivery_address: string | null;
  order_date: string | null;
  requested_delivery_date: string | null;
  contact_person: string | null;
  phone_number: string | null;
  total_price: string | null;
  currency: string | null;
  approved_at: string | null;
  email: {
    sender_email: string;
    reply_to_email: string | null;
    mail_to_email: string | null;
    subject: string;
    received_at: string;
    classification_status: string;
  };
  items: OrderItem[];
  attachments: Array<{ id: string; file_name: string; file_type: string; file_path: string; is_scanned: boolean }>;
  validation_issues: Array<{ id: string; field_name: string; issue_type: string; message: string; severity: string; is_resolved: boolean }>;
  generated_xmls: Array<{ id: string; xml_type: string; file_path: string; status: string; generated_at: string; sent_at: string | null }>;
}
