export interface BusinessRules {
  currency: string;
  freight_enabled: boolean; freight_below: string; freight_charge: string;
  discount_enabled: boolean; discount_from: string; discount_percent: string;
  minimum_enabled: boolean; minimum_order: string;
  review_enabled: boolean; review_from: string;
}

export interface CommercialTerms {
  currency: string; subtotal: string | null; discount: string; freight: string; total: string | null;
  applied: string[]; blockers: string[]; review_required: boolean; enabled: boolean;
}

export interface ClientRules { client_id: string; client_name: string; is_active: boolean; rules: BusinessRules }
export interface ClientCase {
  id: string; client_id: string; client_name: string; label: string; status: string; commercial_terms: CommercialTerms;
}
