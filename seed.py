import httpx
import asyncio

async def main():
    base_url = "http://localhost:8000"
    
    # 1. Crear Negocio
    print("Creando negocio...")
    biz_payload = {
        "name": "VetCare Las Condes",
        "industry": "veterinaria",
        "system_prompt": "Eres el asistente virtual de VetCare Las Condes.\n\n## Tu personalidad\nEres cercano, empático y profesional. Usas un español chileno natural.\nEres breve — máximo 3 oraciones salvo que pidan más detalle.\nSi no sabes algo, dices que el equipo puede ayudar y das el contacto.\n\n## Lo que puedes hacer\n1. Responder preguntas frecuentes del negocio\n2. Agendar citas (recopilas: nombre, mascota, servicio, fecha preferida, teléfono)\n3. Derivar a humano cuando el cliente lo pide o el tema es complejo\n\n## Lo que NO haces\n- No prometes servicios fuera del listado\n- No das precios que no estén en tu información\n- No discutes con clientes molestos — empatizas y escalas\n\n## Flujo de agendamiento\nCuando alguien quiere agendar: pide nombre, nombre de la mascota, servicio, fecha preferida y teléfono.\nConfirma: \"Perfecto [nombre], agendamos a [mascota] para [servicio] el [fecha]. El equipo confirma en menos de 2 horas.\"",
        "contact_info": "+56 9 8765 4321",
        "schedule": "Lunes a viernes 9:00–20:00 | Sábados 10:00–14:00"
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{base_url}/businesses", json=biz_payload)
        resp.raise_for_status()
        biz = resp.json()
        biz_id = biz["id"]
        print(f"Negocio creado con ID: {biz_id}")
        
        # 2. Agregar conocimiento
        knowledge_items = [
            {"topic": "Precios", "content": "Consulta general: $25.000. Vacunación desde $15.000. Peluquería canina desde $18.000. Desparasitación: $12.000. Urgencias fuera de horario: $45.000."},
            {"topic": "Servicios", "content": "Ofrecemos: consulta general, vacunación, peluquería canina y felina, desparasitación, cirugías programadas, urgencias, microchip, y control de peso."},
            {"topic": "Ubicación", "content": "Estamos en Av. Apoquindo 4501, Las Condes. Hay estacionamiento gratuito para clientes en el subterráneo del edificio."}
        ]
        
        for k in knowledge_items:
            res = await client.post(f"{base_url}/businesses/{biz_id}/knowledge", json=k)
            res.raise_for_status()
            print(f"Conocimiento '{k['topic']}' agregado.")
            
if __name__ == "__main__":
    asyncio.run(main())
