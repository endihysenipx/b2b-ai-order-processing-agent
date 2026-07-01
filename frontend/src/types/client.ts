export interface Client {
  id: string;
  client_name: string;
  customer_number: string;
  default_email: string | null;
  email_domain: string;
  extraction_prompt: string;
  required_fields: string[];
  validation_rules: Record<string, unknown>;
  is_active: boolean;
}
