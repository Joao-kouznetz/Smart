# Front

Frontend touch-first do Smart Cart em React + Vite + TypeScript.

## Desenvolvimento

```bash
npm install
npm run dev
```

O frontend usa por padrao o `device_id` persistido no dispositivo como `cart_id`.

Precedencia:

1. `VITE_DEVICE_ID`
2. `?deviceId=...`
3. valor salvo no `localStorage`
4. geracao automatica com persistencia local

## Build

```bash
npm run build
```

Depois do build, o `servidor_central` pode servir a SPA em `/app`.
