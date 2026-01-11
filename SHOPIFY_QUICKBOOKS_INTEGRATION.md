# 🛍️ → 📊 Integración Shopify / QuickBooks Online

## Propuesta Técnica para Tax Triage Workflow

**Sistema:** Multicomm Tax Automation
**Workflow Objetivo:** 🏷️ Tax Triage (CON CONFIG)
**Fecha:** 2026-01-11

---

## 📋 Resumen Ejecutivo

Esta propuesta describe la integración de **Shopify** y **QuickBooks Online** en el flujo Tax Triage para automatizar la gestión de inventario de e-commerce y sincronización contable, eliminando facturas duplicadas y mejorando la precisión fiscal.

**Objetivo Principal:** Sincronizar transacciones de Shopify con QuickBooks Online de forma automática, detectando duplicados y categorizando correctamente ingresos para preparación fiscal.

---

## 🏗️ Arquitectura Propuesta

### Flujo de Integración:

```
┌─────────────────┐
│  Tax Triage     │
│   Webhook       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│ Detect E-comm   │────▶ │ Load Config      │
│   Business      │      │    Global        │
└────────┬────────┘      └──────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│     SHOPIFY INTEGRATION MODULE              │
├─────────────────────────────────────────────┤
│ 1. Fetch Recent Orders (Last 30 days)       │
│ 2. Get Product Inventory Levels             │
│ 3. Calculate Sales Summary                  │
│ 4. Detect Tax Implications (Nexus)          │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│   QUICKBOOKS ONLINE INTEGRATION MODULE      │
├─────────────────────────────────────────────┤
│ 1. Search for Existing Invoices (by Order#) │
│ 2. Check for Duplicates                     │
│ 3. Create/Update Invoices                   │
│ 4. Categorize Income Accounts               │
│ 5. Apply Tax Rates (by Province/State)      │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  Sync Summary   │────▶ │  Save to         │
│   to Airtable   │      │  Tax_Cases       │
└─────────────────┘      └──────────────────┘
         │
         ▼
┌─────────────────┐
│   Response to   │
│     Client      │
└─────────────────┘
```

---

## 🔧 Implementación Técnica

### Paso 1: Modificar Tax Triage para Detectar E-commerce

Agregar después del nodo `Parse Triage Data` (línea 50):

```javascript
// DETECT E-COMMERCE BUSINESS - NEW NODE
const client = $input.first().json;
const CONFIG = client._config;

// Detectar si es negocio de e-commerce
const isEcommerce = Boolean(
  client.business?.has_business &&
  (client.business?.business_type === 'ecommerce' ||
   client.business?.business_type === 'online_sales' ||
   client.business?.uses_shopify ||
   client.business?.annual_revenue > CONFIG.GST_THRESHOLD)
);

return {
  json: {
    ...client,
    is_ecommerce: isEcommerce,
    requires_inventory_sync: isEcommerce && client.business?.uses_shopify
  }
};
```

---

### Paso 2: Nodo Shopify - Fetch Orders & Inventory

**Nodo n8n:** `Shopify` (integración nativa)

#### Configuración:

```json
{
  "operation": "getAll",
  "resource": "order",
  "filters": {
    "created_at_min": "={{ $now.minus({ days: 30 }).toISO() }}",
    "status": "any",
    "financial_status": "paid"
  },
  "returnAll": true,
  "options": {
    "fields": [
      "id",
      "order_number",
      "created_at",
      "total_price",
      "subtotal_price",
      "total_tax",
      "currency",
      "financial_status",
      "line_items",
      "customer",
      "shipping_address",
      "billing_address"
    ]
  }
}
```

#### Salida Esperada:

```json
{
  "shopify_orders": [
    {
      "id": 4567890123,
      "order_number": 1001,
      "created_at": "2026-01-05T14:30:00-05:00",
      "total_price": "150.00",
      "total_tax": "19.50",
      "currency": "CAD",
      "financial_status": "paid",
      "customer": {
        "email": "customer@example.com"
      },
      "shipping_address": {
        "province_code": "ON",
        "country_code": "CA"
      },
      "line_items": [
        {
          "product_id": 789012345,
          "title": "Widget Pro",
          "quantity": 2,
          "price": "65.00"
        }
      ]
    }
  ]
}
```

---

### Paso 3: Procesamiento de Órdenes Shopify

**Nodo Code:** Process Shopify Data

```javascript
// PROCESS SHOPIFY ORDERS - CON CONFIG
try {
  const client = $('Detect E-commerce').item.json;
  const CONFIG = client._config;
  const shopifyOrders = $input.all().map(item => item.json);

  // Agrupar por provincia/estado para nexus detection
  let salesByJurisdiction = {};
  let totalRevenue = 0;
  let totalTaxCollected = 0;
  let orderSummary = [];

  shopifyOrders.forEach(order => {
    const jurisdiction = order.shipping_address?.province_code ||
                        order.shipping_address?.country_code ||
                        'UNKNOWN';

    const revenue = parseFloat(order.total_price) || 0;
    const tax = parseFloat(order.total_tax) || 0;

    // Acumular por jurisdicción
    if (!salesByJurisdiction[jurisdiction]) {
      salesByJurisdiction[jurisdiction] = {
        revenue: 0,
        tax: 0,
        orders: 0,
        country: order.shipping_address?.country_code || 'CA'
      };
    }

    salesByJurisdiction[jurisdiction].revenue += revenue;
    salesByJurisdiction[jurisdiction].tax += tax;
    salesByJurisdiction[jurisdiction].orders += 1;

    totalRevenue += revenue;
    totalTaxCollected += tax;

    // Preparar para QuickBooks
    orderSummary.push({
      shopify_order_id: order.id,
      order_number: order.order_number,
      created_at: order.created_at,
      customer_email: order.customer?.email || 'unknown@example.com',
      total: revenue,
      tax: tax,
      jurisdiction: jurisdiction,
      currency: order.currency || 'CAD',
      line_items: order.line_items || []
    });
  });

  // Detectar nexus (umbrales para GST/HST y nexus USA)
  let nexusFlags = [];
  Object.keys(salesByJurisdiction).forEach(jurisdiction => {
    const data = salesByJurisdiction[jurisdiction];

    // Canada GST/HST
    if (data.country === 'CA' && data.revenue >= CONFIG.GST_THRESHOLD) {
      nexusFlags.push(`NEXUS_CA_${jurisdiction}`);
    }

    // USA Economic Nexus
    if (data.country === 'US') {
      const stateThreshold = CONFIG.usa?.NEXUS_THRESHOLDS?.[jurisdiction] ||
                             CONFIG.usa?.NEXUS_THRESHOLDS?.DEFAULT;
      if (data.revenue >= stateThreshold.sales) {
        nexusFlags.push(`NEXUS_US_${jurisdiction}`);
      }
    }
  });

  return { json: {
    ...client,
    shopify_sync: {
      total_orders: shopifyOrders.length,
      total_revenue: totalRevenue.toFixed(2),
      total_tax_collected: totalTaxCollected.toFixed(2),
      sales_by_jurisdiction: salesByJurisdiction,
      nexus_flags: nexusFlags,
      requires_multistate_filing: nexusFlags.length > 1,
      orders_for_qbo: orderSummary,
      synced_at: new Date().toISOString()
    }
  }};

} catch (error) {
  const client = $('Detect E-commerce').item.json;
  return { json: {
    ...client,
    shopify_sync: {
      error: error.message,
      total_orders: 0
    }
  }};
}
```

---

### Paso 4: QuickBooks Online - Búsqueda de Duplicados

**Nodo Code:** Check QBO Duplicates

```javascript
// PREPARE QBO DUPLICATE CHECK
const client = $input.first().json;
const ordersToSync = client.shopify_sync?.orders_for_qbo || [];

// Crear búsquedas para cada orden (se ejecutarán en paralelo)
const searchQueries = ordersToSync.map(order => ({
  json: {
    order_number: order.order_number,
    shopify_order_id: order.shopify_order_id,
    total: order.total,
    customer_email: order.customer_email,
    search_query: `SELECT * FROM Invoice WHERE DocNumber = '${order.order_number}' MAXRESULTS 1`
  }
}));

return searchQueries;
```

**Nodo QuickBooks Online:** Query Invoices

```json
{
  "operation": "executeQuery",
  "query": "={{ $json.search_query }}"
}
```

---

### Paso 5: Crear/Actualizar Facturas en QuickBooks

**Nodo Code:** Map Shopify to QuickBooks Format

```javascript
// MAP SHOPIFY ORDERS TO QUICKBOOKS INVOICES - CON CONFIG
try {
  const client = $('Process Shopify Data').item.json;
  const CONFIG = client._config;
  const qboSearchResults = $input.all();
  const ordersToSync = client.shopify_sync?.orders_for_qbo || [];

  // Mapear resultados de búsqueda
  let existingInvoices = {};
  qboSearchResults.forEach((result, index) => {
    const orderNum = ordersToSync[index]?.order_number;
    if (result.json?.QueryResponse?.Invoice?.length > 0) {
      existingInvoices[orderNum] = result.json.QueryResponse.Invoice[0];
    }
  });

  // Preparar facturas para crear/actualizar
  let invoicesToCreate = [];
  let invoicesToUpdate = [];
  let skippedDuplicates = [];

  ordersToSync.forEach(order => {
    const existing = existingInvoices[order.order_number];

    if (existing) {
      // Verificar si los montos coinciden
      const existingTotal = parseFloat(existing.TotalAmt || 0);
      const newTotal = parseFloat(order.total);

      if (Math.abs(existingTotal - newTotal) < 0.01) {
        // Duplicado exacto - omitir
        skippedDuplicates.push({
          order_number: order.order_number,
          reason: 'Exact duplicate found',
          qbo_invoice_id: existing.Id
        });
      } else {
        // Actualizar (monto diferente)
        invoicesToUpdate.push({
          Id: existing.Id,
          DocNumber: order.order_number,
          TxnDate: order.created_at.split('T')[0],
          CustomerRef: {
            value: "1" // TODO: crear/buscar cliente por email
          },
          Line: order.line_items.map((item, idx) => ({
            DetailType: "SalesItemLineDetail",
            Amount: parseFloat(item.price) * item.quantity,
            SalesItemLineDetail: {
              ItemRef: {
                value: "1" // TODO: mapear productos
              },
              Qty: item.quantity,
              UnitPrice: parseFloat(item.price),
              TaxCodeRef: {
                value: determineTaxCode(order.jurisdiction, CONFIG)
              }
            },
            Description: item.title
          })),
          TxnTaxDetail: {
            TotalTax: order.tax
          },
          CustomField: [
            {
              DefinitionId: "1",
              Name: "Shopify Order ID",
              Type: "StringType",
              StringValue: order.shopify_order_id.toString()
            }
          ]
        });
      }
    } else {
      // Crear nueva factura
      invoicesToCreate.push({
        DocNumber: order.order_number,
        TxnDate: order.created_at.split('T')[0],
        CustomerRef: {
          value: "1" // TODO: crear/buscar cliente
        },
        Line: order.line_items.map((item, idx) => ({
          DetailType: "SalesItemLineDetail",
          Amount: parseFloat(item.price) * item.quantity,
          SalesItemLineDetail: {
            ItemRef: {
              value: "1" // TODO: mapear productos
            },
            Qty: item.quantity,
            UnitPrice: parseFloat(item.price),
            TaxCodeRef: {
              value: determineTaxCode(order.jurisdiction, CONFIG)
            }
          },
          Description: item.title
        })),
        TxnTaxDetail: {
          TotalTax: order.tax
        },
        CustomField: [
          {
            DefinitionId: "1",
            Name: "Shopify Order ID",
            Type: "StringType",
            StringValue: order.shopify_order_id.toString()
          }
        ]
      });
    }
  });

  // Función helper para determinar código de impuesto
  function determineTaxCode(jurisdiction, config) {
    // GST/HST para provincias canadienses
    if (config.canada.HST_PROVINCES.includes(jurisdiction)) {
      return "HST"; // 13% Ontario, etc.
    } else if (config.canada.GST_ONLY_PROVINCES.includes(jurisdiction)) {
      if (jurisdiction === 'QC') return "GST+QST"; // 5% + 9.975%
      return "GST"; // 5% federal
    }

    // USA - varía por estado
    if (jurisdiction.length === 2 && jurisdiction !== 'CA') {
      return `US_${jurisdiction}_TAX`;
    }

    return "TAX"; // Default
  }

  return { json: {
    ...client,
    qbo_sync: {
      invoices_to_create: invoicesToCreate,
      invoices_to_update: invoicesToUpdate,
      skipped_duplicates: skippedDuplicates,
      summary: {
        to_create: invoicesToCreate.length,
        to_update: invoicesToUpdate.length,
        skipped: skippedDuplicates.length,
        total_processed: ordersToSync.length
      }
    }
  }};

} catch (error) {
  const client = $input.first().json;
  return { json: {
    ...client,
    qbo_sync: { error: error.message }
  }};
}
```

---

### Paso 6: Ejecutar Sincronización con QuickBooks

**Nodo QuickBooks Online (Loop):** Create Invoices

Para cada factura en `invoices_to_create`:

```json
{
  "operation": "create",
  "resource": "invoice",
  "data": "={{ $json }}"
}
```

**Nodo QuickBooks Online (Loop):** Update Invoices

Para cada factura en `invoices_to_update`:

```json
{
  "operation": "update",
  "resource": "invoice",
  "invoiceId": "={{ $json.Id }}",
  "data": "={{ $json }}"
}
```

---

## 🗺️ Mapeo de Datos: Shopify ↔ QuickBooks

### Entidades Principales:

| Shopify | QuickBooks Online | Notas |
|---------|-------------------|-------|
| `order.order_number` | `Invoice.DocNumber` | Clave para prevenir duplicados |
| `order.id` | `Invoice.CustomField[Shopify Order ID]` | Tracking interno |
| `order.created_at` | `Invoice.TxnDate` | Fecha de transacción |
| `order.customer.email` | `Customer.PrimaryEmailAddr` | Buscar/crear cliente |
| `order.total_price` | `Invoice.TotalAmt` | Validación de duplicados |
| `order.total_tax` | `Invoice.TxnTaxDetail.TotalTax` | Impuestos |
| `line_items[].title` | `InvoiceLine.Description` | Descripción del producto |
| `line_items[].product_id` | `InvoiceLine.SalesItemLineDetail.ItemRef` | Mapear a Items en QBO |
| `line_items[].quantity` | `InvoiceLine.SalesItemLineDetail.Qty` | Cantidad |
| `line_items[].price` | `InvoiceLine.SalesItemLineDetail.UnitPrice` | Precio unitario |
| `shipping_address.province_code` | `TaxCodeRef` | Determina tasa de impuesto |

---

## 🚫 Prevención de Duplicados

### Estrategia Multi-Capa:

#### 1. **Búsqueda por DocNumber (Order Number)**
```sql
SELECT * FROM Invoice WHERE DocNumber = 'SHOPIFY_ORDER_NUMBER'
```

#### 2. **Validación por Custom Field**
```sql
SELECT * FROM Invoice WHERE CustomField.StringValue = 'SHOPIFY_ORDER_ID'
```

#### 3. **Verificación de Monto**
Si se encuentra una factura con el mismo `DocNumber`:
- Comparar `TotalAmt`
- Si coincide dentro de ±$0.01 → DUPLICADO EXACTO → Omitir
- Si difiere → Potencial actualización (requiere revisión manual)

#### 4. **Log de Sincronización en Airtable**
Guardar en tabla `Tax_Cases` o nueva tabla `QBO_Sync_Log`:
```javascript
{
  shopify_order_id: "4567890123",
  qbo_invoice_id: "123",
  sync_status: "created" | "updated" | "skipped_duplicate",
  synced_at: "2026-01-11T10:30:00Z",
  amount: 150.00
}
```

---

## 📊 Categorización de Ingresos por Cuenta

### Cuentas Recomendadas en QuickBooks:

| Tipo de Ingreso | Cuenta QBO | Código | Notas |
|------------------|------------|--------|-------|
| **Ventas Online (Canadá)** | Sales - Online Canada | 4000-CA | Ventas domésticas |
| **Ventas Online (USA)** | Sales - Online USA | 4000-US | Ventas internacionales |
| **Ventas con GST** | Sales - GST Applied | 4010-GST | Provincias GST-only |
| **Ventas con HST** | Sales - HST Applied | 4010-HST | ON, NB, NS, NL, PE |
| **Ventas QC (GST+QST)** | Sales - Quebec | 4010-QC | Quebec específico |
| **Envíos** | Shipping Revenue | 4100 | Ingresos por envío |
| **Devoluciones** | Sales Returns | 4900 | Contra-cuenta |

### Reglas de Categorización:

```javascript
function determineIncomeAccount(order, CONFIG) {
  const jurisdiction = order.jurisdiction;
  const country = salesByJurisdiction[jurisdiction]?.country || 'CA';

  // USA
  if (country === 'US') {
    return { account: "4000-US", name: "Sales - Online USA" };
  }

  // Canada - por provincia
  if (CONFIG.canada.HST_PROVINCES.includes(jurisdiction)) {
    return { account: "4010-HST", name: "Sales - HST Applied" };
  }

  if (jurisdiction === 'QC') {
    return { account: "4010-QC", name: "Sales - Quebec" };
  }

  if (CONFIG.canada.GST_ONLY_PROVINCES.includes(jurisdiction)) {
    return { account: "4010-GST", name: "Sales - GST Applied" };
  }

  // Default
  return { account: "4000-CA", name: "Sales - Online Canada" };
}
```

---

## 🧪 Ejemplo de Flujo Completo

### Input (Webhook Tax Triage):

```json
{
  "name": "Jane's Boutique",
  "email": "jane@boutique.ca",
  "entity_type": "corporation",
  "business": {
    "has_business": true,
    "business_type": "ecommerce",
    "uses_shopify": true,
    "annual_revenue": 500000
  }
}
```

### Paso 1: Detect E-commerce
```json
{
  "is_ecommerce": true,
  "requires_inventory_sync": true
}
```

### Paso 2: Fetch Shopify (últimos 30 días)
- 45 órdenes encontradas
- Total ventas: $15,230.00
- Total impuestos: $1,980.00

### Paso 3: Process Shopify Data
```json
{
  "shopify_sync": {
    "total_orders": 45,
    "total_revenue": "15230.00",
    "sales_by_jurisdiction": {
      "ON": { "revenue": 8500, "orders": 25 },
      "QC": { "revenue": 4200, "orders": 12 },
      "BC": { "revenue": 2530, "orders": 8 }
    },
    "nexus_flags": ["NEXUS_CA_ON", "NEXUS_CA_QC", "NEXUS_CA_BC"]
  }
}
```

### Paso 4: Check QBO Duplicates
- 45 búsquedas ejecutadas
- 10 facturas existentes encontradas
- 35 nuevas órdenes para sincronizar

### Paso 5: Map to QBO
```json
{
  "qbo_sync": {
    "summary": {
      "to_create": 35,
      "to_update": 2,
      "skipped": 8,
      "total_processed": 45
    }
  }
}
```

### Paso 6: Execute QBO Sync
- ✅ 35 facturas creadas
- ✅ 2 facturas actualizadas
- ⏭️ 8 duplicados omitidos

### Output Final:
```json
{
  "success": true,
  "client_name": "Jane's Boutique",
  "shopify_orders_synced": 37,
  "qbo_invoices_created": 35,
  "qbo_invoices_updated": 2,
  "duplicates_prevented": 8,
  "multi_province_nexus": true,
  "provinces_affected": ["ON", "QC", "BC"],
  "total_revenue_synced": "$15,230.00",
  "message": "Shopify inventory synced to QuickBooks. Multi-province nexus detected."
}
```

---

## 🔐 Seguridad y Credenciales

### Credenciales Requeridas:

#### Shopify:
- **Tipo:** OAuth 2.0 o API Key
- **Permisos:**
  - `read_orders`
  - `read_products`
  - `read_inventory`
- **Guardar en n8n:** Credentials → Shopify → "Multicomm Shopify"

#### QuickBooks Online:
- **Tipo:** OAuth 2.0
- **Permisos:**
  - `com.intuit.quickbooks.accounting` (full access)
- **Guardar en n8n:** Credentials → QuickBooks Online → "Multicomm QBO"

### Almacenamiento Seguro:
```javascript
// En 00-Config Global
CREDENTIALS: {
  // ...existing credentials
  SHOPIFY_CREDENTIAL_ID: 'YOUR_SHOPIFY_CRED_ID',
  SHOPIFY_STORE_NAME: 'your-store.myshopify.com',
  QBO_CREDENTIAL_ID: 'YOUR_QBO_CRED_ID',
  QBO_COMPANY_ID: 'YOUR_QBO_COMPANY_ID'
}
```

---

## ⚙️ Configuración en Config Global

Agregar a `00-Config Global.json`:

```javascript
// ECOMMERCE INTEGRATION CONFIG
ECOMMERCE: {
  // Shopify
  shopify: {
    sync_interval_days: 30,
    auto_sync_enabled: true,
    inventory_threshold: 10 // alerta si inventario < 10
  },

  // QuickBooks Online
  quickbooks: {
    default_customer_id: '1', // Cliente genérico "Online Sales"
    default_payment_term: 'Due on receipt',
    auto_create_customers: true,
    income_accounts: {
      'CA': '4000-CA',
      'US': '4000-US',
      'ON': '4010-HST',
      'QC': '4010-QC',
      'DEFAULT': '4000-CA'
    },
    tax_codes: {
      'HST': 'HST-13%',
      'GST': 'GST-5%',
      'GST+QST': 'QC-14.975%',
      'EXEMPT': 'TAX-EXEMPT'
    }
  },

  // Duplicate Prevention
  duplicate_detection: {
    enabled: true,
    match_threshold_cents: 1, // Considerar duplicado si diferencia < $0.01
    update_existing: false, // No actualizar automáticamente
    skip_on_duplicate: true
  }
}
```

---

## 📈 Métricas y Reportes

### KPIs a Trackear:

```javascript
{
  sync_metrics: {
    last_sync_date: "2026-01-11T10:30:00Z",
    orders_synced_total: 1250,
    orders_synced_30d: 45,
    duplicates_prevented: 8,
    sync_errors: 0,
    avg_sync_time_seconds: 12.5,
    revenue_synced_30d: 15230.00
  }
}
```

### Guardar en Airtable:
- Tabla: `Tax_Cases` (agregar campos)
  - `Shopify Orders Synced` (Number)
  - `QBO Invoices Created` (Number)
  - `Last Sync Date` (Date)
  - `Sync Status` (Single select: Success, Failed, Partial)

---

## 🛠️ Pasos de Implementación

### Fase 1: Setup (1-2 días)
- [ ] Configurar credenciales Shopify en n8n
- [ ] Configurar credenciales QuickBooks Online en n8n
- [ ] Actualizar `00-Config Global` con config de e-commerce
- [ ] Crear cuentas de ingresos en QuickBooks

### Fase 2: Desarrollo (3-5 días)
- [ ] Agregar nodo "Detect E-commerce" a Tax Triage
- [ ] Implementar nodos Shopify (Fetch Orders, Inventory)
- [ ] Implementar nodo "Process Shopify Data"
- [ ] Implementar lógica de búsqueda de duplicados
- [ ] Implementar mapeo Shopify → QuickBooks
- [ ] Implementar creación/actualización de facturas

### Fase 3: Testing (2-3 días)
- [ ] Probar con datos de prueba en Shopify test store
- [ ] Validar prevención de duplicados
- [ ] Verificar categorización de cuentas
- [ ] Probar con órdenes multi-provincia
- [ ] Validar cálculos de impuestos

### Fase 4: Despliegue (1 día)
- [ ] Activar en producción
- [ ] Monitorear primeras sincronizaciones
- [ ] Documentar casos edge
- [ ] Capacitar al equipo

---

## ⚠️ Consideraciones y Limitaciones

### API Rate Limits:
- **Shopify:** 2 requests/second (Shopify Plus: 4 req/s)
- **QuickBooks Online:** 500 requests/minute por company

**Solución:** Implementar batching y throttling en n8n

### Sincronización Histórica:
- Por defecto: últimos 30 días
- Para histórico completo: ejecutar script one-time separado

### Productos No Mapeados:
- Si producto Shopify no existe en QBO → crear automáticamente o usar producto genérico "Online Sale"

### Clientes Anónimos:
- Si no hay email → usar cliente genérico "Guest Checkout"

### Reembolsos y Devoluciones:
- Fase 1: No incluido (solo ventas)
- Fase 2 (futura): sincronizar credit memos

---

## 📞 Soporte y Documentación

### Recursos:
- [Shopify Admin API Docs](https://shopify.dev/docs/api/admin-rest)
- [QuickBooks Online API Docs](https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/invoice)
- [n8n Shopify Integration](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.shopify/)
- [n8n QuickBooks Integration](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.quickbooksonline/)

### Mantenimiento:
- Revisar logs semanalmente
- Validar sincronización mensual
- Actualizar mapeo de productos trimestralmente

---

## ✅ Checklist de Validación

Antes de considerar completa la integración:

- [ ] ✅ Órdenes de Shopify se sincronizan automáticamente
- [ ] ✅ No se crean facturas duplicadas en QuickBooks
- [ ] ✅ Impuestos se calculan correctamente por provincia
- [ ] ✅ Cuentas de ingresos se categorizan apropiadamente
- [ ] ✅ Nexus multi-provincia se detecta y se reporta
- [ ] ✅ Errores se logean en Error_Logs de Airtable
- [ ] ✅ Cliente recibe confirmación de sincronización
- [ ] ✅ Dashboard muestra métricas de sincronización

---

*Propuesta técnica generada por Claude Code*
*Multicomm Tax Automation System*
