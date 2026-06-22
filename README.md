# Marketplace Pricing Calculator — México 2026

Calculadora de precios para **Mercado Libre México** y **Amazon México** con comisiones reales 2026, sincronización con Shopify morekashop1.

## 🚀 Deploy en Streamlit Cloud

1. Sube este repo a GitHub: `morekaoficial-lgtm/marketplace-pricing-calculator`
2. Ve a https://share.streamlit.io
3. Conecta el repo
4. ¡Listo!

## 🔐 Configuración de Secrets (Obligatorio para Shopify Sync)

Para conectar con Shopify morekashop1, debes configurar el token en los **Secrets** de Streamlit Cloud:

1. Ve a tu app en [share.streamlit.io](https://share.streamlit.io)
2. Click en **Settings** (⚙️)
3. Ve a **Secrets**
4. Agrega:

```toml
[shopify]
MOREKA_ACCESS_TOKEN = "tu_token_aqui"
```

5. Click **Save**

**Nota:** El token nunca se guarda en el código. Se lee desde `st.secrets` en tiempo de ejecución.

## 📊 Funciones

### 🧮 Calculadora Manual (Tab 1)
- Ingresa **costo** y **margen deseado**
- Selecciona **categoría** para ML y Amazon
- Calcula **precio base** con comisiones reales 2026
- Evalúa **descuentos** (5%, 10%, 20%, 30%, 40%, 50%)
- ⚠️ **Alertas** si un descuento te hace perder dinero
- **Desglose completo** de comisiones: ML (comisión + IVA + ISR + costo fijo) | Amazon (referral + FBA + plan)

### 📊 Comparador ML vs Amazon (Tab 2)
- Compara el **mismo producto** en ambos marketplaces
- Te dice cuál es **más rentable**
- Precios con descuentos en ambos

### 🔄 Sincronizar Shopify (Tab 3)
- Conecta con **morekashop1** automáticamente
- Carga todos los productos con sus **costos**
- Calcula precios para **todos los productos** de una vez
- Exporta a **CSV o Excel**

## 💰 Comisiones México 2026 (Actualizadas)

### Mercado Libre México
| Concepto | Detalle |
|---|---|
| **Comisión Clásica** | 8-15% según categoría |
| **Comisión Premium** | 12.5-20.5% según categoría |
| **Costo fijo adicional** | $25-$37/unidad (solo Clásica, precio < $299) |
| **IVA retenido** | 8% sobre base gravable (con RFC) / 16% (sin RFC) |
| **ISR retenido** | 2.5% sobre base gravable (con RFC) / 20% sobre precio total (sin RFC) |
| **Envío** | Configurable: gratis o comprador paga |

### Amazon México
| Concepto | Detalle |
|---|---|
| **Plan Profesional** | $600 MXN/mes |
| **Plan Individual** | $10 MXN por venta |
| **Referral Fee** | 8-20% según categoría |
| **Tarifa mínima** | $5 MXN por artículo (algunas categorías) |
| **FBA** | Configurable por unidad |
| **FBM** | Envío configurable por vendedor |

## ⚙️ Configuración (sidebar)

- **RFC:** ¿Tienes RFC registrado en ML? (afecta IVA/ISR)
- **Tipo publicación ML:** Clásica o Premium
- **Envío ML:** Gratis o comprador paga
- **Plan Amazon:** Profesional o Individual
- **FBA:** ¿Usas FBA? ¿Cuánto cuesta por unidad?
- **Descuentos:** Qué niveles evaluar (5%, 10%, 20%, etc.)

## 📝 Shopify Sync

La app se conecta a **morekashop1** para obtener:
- Lista de productos
- SKUs
- Costos unitarios (desde `inventory_items.cost`)

**Requisito:** Los costos deben estar configurados en Shopify Admin > Productos > Inventario > Costo por artículo.

## 📁 Estructura

```
marketplace-pricing-calculator/
├── app.py              # App principal (~500 líneas)
├── requirements.txt    # Dependencias
├── README.md           # Este archivo
├── QUICKREF.md         # Referencia rápida
└── .streamlit/
    └── config.toml     # Tema personalizado
```

## 🛠️ Categorías soportadas

### Mercado Libre (25 categorías)
Celulares, Computación, Electrónica, Cámaras, Instrumentos, Consolas, Agro, Alimentos, Accesorios Vehículos, Industrias, Herramientas, Belleza, Salud, Electrodomésticos, Deportes, Hogar, Juguetes, Joyas, Libros, Mascotas, Ropa, Bebés, Construcción, etc.

### Amazon (18 categorías)
Electrónica de Consumo, Computadoras, Belleza, Hogar, Juguetes, Deportes, Herramientas, Automotriz, Joyas, Relojes, Ropa, Instrumentos, Libros, Mascotas, Todo lo demás, etc.

## 📝 Notas importantes

- **Comisiones actualizadas:** Junio 2026 (fuente: SAT, Mercado Libre, Amazon Seller Central)
- **ISR ML 2026:** Subió de 1% a 2.5% (Ley de Ingresos 2026)
- **IVA retenido:** Acreditable en declaración mensual (con RFC)
- **Sin RFC:** Penalización fiscal significativa (IVA 16% + ISR 20%)

## 🔗 Links

- **Repo:** https://github.com/morekaoficial-lgtm/marketplace-pricing-calculator
- **Streamlit Cloud:** https://share.streamlit.io

---

*Creado: Junio 2026 | Actualizado: Junio 2026*
