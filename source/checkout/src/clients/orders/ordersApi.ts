/**
 * Orders Service API Client
 * Generated from source/orders/openapi.yml
 * Uses native fetch (Node 18+) — zero external dependencies
 */

import { Order, ExistingOrder } from './models';

export class OrdersApi {
  private basePath: string;

  constructor(basePath: string) {
    // Strip trailing slash if present
    this.basePath = basePath.replace(/\/+$/, '');
  }

  /**
   * Create an order
   * POST /orders
   */
  async createOrder(order: Order): Promise<ExistingOrder> {
    const response = await fetch(`${this.basePath}/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(order),
    });

    if (!response.ok) {
      throw new Error(`Orders API error: ${response.status} ${response.statusText}`);
    }

    return response.json() as Promise<ExistingOrder>;
  }

  /**
   * List orders
   * GET /orders
   */
  async listOrders(): Promise<ExistingOrder[]> {
    const response = await fetch(`${this.basePath}/orders`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Orders API error: ${response.status} ${response.statusText}`);
    }

    return response.json() as Promise<ExistingOrder[]>;
  }
}
