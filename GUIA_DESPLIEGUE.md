# Guía de Despliegue - App SAC en Railway

## Paso 1: Actualizar el repositorio en GitHub

Desde Git Bash en tu PC:

```bash
cd "/c/Users/LENOVO/OneDrive/Escritorio/carpeta de cowork/reporte automatizado sac/app_sac_github"
git add .
git commit -m "Agregar descarga automática y Dockerfile para Railway"
git push
```

## Paso 2: Crear cuenta en Railway

1. Ve a **https://railway.app**
2. Clic en **"Login"** → **"Login with GitHub"**
3. Autoriza el acceso

## Paso 3: Crear el proyecto

1. En el dashboard, clic en **"New Project"**
2. Selecciona **"Deploy from GitHub Repo"**
3. Busca y selecciona tu repo **`app-sac`**
4. Railway detectará automáticamente el Dockerfile y empezará a construir

## Paso 4: Configurar credenciales (Variables de entorno)

1. En tu proyecto de Railway, ve a la pestaña **"Variables"**
2. Agrega estas variables:

```
RIMAC_EMAIL = tu_email_rimac
RIMAC_PASSWORD = tu_contraseña_rimac
LP_USUARIO = tu_usuario_lp
LP_PASSWORD = tu_contraseña_lp
```

3. Railway reiniciará la app automáticamente

## Paso 5: Configurar el dominio público

1. Ve a **Settings** de tu servicio
2. En la sección **"Networking"**, clic en **"Generate Domain"**
3. Te dará una URL tipo: `https://app-sac-production-xxxx.up.railway.app`
4. Comparte esta URL con tu equipo

## Paso 6: Configurar Streamlit Secrets (alternativa)

Si prefieres usar Streamlit secrets en vez de variables de entorno:

1. En tu proyecto, crea el archivo `.streamlit/secrets.toml` (NO lo subas a GitHub)
2. En Railway, puedes crear un volumen o usar variables de entorno (recomendado)

## Costos

Railway ofrece un trial gratuito de $5 USD. Después:
- Plan Hobby: $5/mes + uso (típicamente $5-10/mes total para esta app)
- La app usa ~512MB RAM y poco CPU (solo durante generación de reportes)

## Actualizar la app

Cada vez que hagas `git push`, Railway re-despliega automáticamente.
