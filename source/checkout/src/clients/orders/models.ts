/**
 * Orders Service - Model definitions
 * Auto-generated from source/orders/openapi.yml using typescript-fetch pattern
 */

export interface OrderItem {
  productId?: string;
  quantity?: number;
  price?: number;
}

export interface Order {
  firstName?: string;
  lastName?: string;
  email?: string;
  items?: OrderItem[];
}

export interface ExistingOrder {
  id?: string;
  firstName?: string;
  lastName?: string;
  email?: string;
  items?: OrderItem[];
}
