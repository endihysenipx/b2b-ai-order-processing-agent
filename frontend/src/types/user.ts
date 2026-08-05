export interface User {
  id: string;
  full_name: string;
  email: string;
  role: string;
  totp_enabled: boolean;
  client_ids: string[];
  is_active?: boolean;
}
