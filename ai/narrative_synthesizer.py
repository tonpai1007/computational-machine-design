"""
Academic Narrative Synthesizer Module for MDIE.

Provides AI-assisted technical narrative synthesis for academic engineering reports
using LLMRouter (Gemini, Groq, OpenRouter, Ollama) with a robust domain-aware fallback.
Strictly adheres to MDIE Directives:
- AI proposes/synthesizes contextual descriptive narratives, objectives, and mechanical roles.
- Numerical engineering values (stresses, buckling loads, safety factors) remain 100% deterministic physics.
"""

import json
import logging
from typing import Any

from ai.llm_router import LLMRouter
from core.frame_model import FrameDesignModel

logger = logging.getLogger("ai.narrative_synthesizer")


def synthesize_academic_narrative(
    model: FrameDesignModel, component_names: list[str], use_ai: bool = True
) -> dict[str, Any]:
    """
    Synthesize introduction (บทนำ) and component mechanical role descriptions
    using LLMRouter (AI) with a deterministic domain-aware fallback.
    """
    g = model.geometry
    loads = model.loads
    m = model.material

    system_prompt = (
        "คุณคืออาจารย์ผู้เชี่ยวชาญการสอนวิชาการออกแบบเครื่องจักรกล (Machine Design) "
        "จงเขียนเนื้อหาบทนำเชิงวิชาการ (บทนำ) และคำอธิบายทางกลของชิ้นส่วนสำหรับรายงานโครงงานวิชาการ "
        "ตามมาตรฐานหลักสูตรวิศวกรรมเครื่องกลไทย (เช่น สจล., มจพ., จุฬาฯ) ให้ตอบเป็น JSON เท่านั้น"
    )
    user_prompt = (
        f"ชื่อโครงงาน/เครื่องจักร: {model.name}\n"
        f"ประเภทโครงสร้าง: {g.topology_type} (จำนวนเสารองรับ {g.num_legs} ขา)\n"
        f"วัสดุหลัก: {m.name} (Yield = {m.yield_strength_mpa} MPa, Ultimate = {m.ultimate_strength_mpa} MPa, E = {m.elastic_modulus_gpa} GPa)\n"
        f"ภาระบรรทุกใช้งานหลัก: {loads.seat_vertical_load_n:.0f} N\n"
        f"รายการชิ้นส่วนที่ต้องอธิบาย: {', '.join(component_names)}\n\n"
        "จงตอบ JSON ที่มีคีย์ดังนี้:\n"
        "1. 'introduction': ข้อความบทนำ 2 ย่อหน้า อธิบายความสำคัญ วัตถุประสงค์การออกแบบ สรีรศาสตร์ ภาระบรรทุก และเกณฑ์ความปลอดภัย\n"
        "2. 'components': ออบเจกต์ที่แมปชื่อชิ้นส่วนแต่ละชิ้นเข้ากับคำอธิบายหน้าที่ทางกลศาสตร์ (2-3 ประโยค)"
    )

    if use_ai:
        try:
            resp, provider, logs = LLMRouter.call_chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format_json=True,
                max_tokens=1000,
                temperature=0.2,
            )
            if resp:
                data = json.loads(resp)
                if "introduction" in data and "components" in data:
                    return dict(data)
        except Exception as e:
            logger.debug(f"AI narrative call note: {e}")

    # Domain-aware programmatic synthesizer fallback (never hardcoded to a single chair or student)
    topo_th = {
        "chair": "เก้าอี้พักผ่อนโครงสร้างตามหลักสรีรศาสตร์ (Ergonomic Chair)",
        "stool": "เก้าอี้สตูลโครงสร้างรับน้ำหนัก (Structural Stool)",
        "table": "โต๊ะโครงสร้างรับภาระบรรทุก (Structural Table)",
        "bench": "ม้านั่งยาวโครงสร้างรับภาระบรรทุก (Structural Bench)",
    }.get(g.topology_type, f"โครงสร้างเครื่องจักรกล ({model.name})")

    intro = (
        f"ปัจจุบันโครงสร้าง {model.name} ซึ่งจัดเป็น {topo_th} มีบทบาทสำคัญอย่างยิ่งต่อการใช้งานอย่างปลอดภัยตามหลักสรีรศาสตร์และวิศวกรรมเครื่องกล "
        f"โดยโครงสร้างต้องสามารถรองรับภาระน้ำหนักบรรทุกใช้งานจริง (Service Payload) ได้อย่างมั่นคงและปลอดภัย "
        f"การออกแบบคำนึงถึงภาระบรรทุกกดแนวดิ่งหลัก {loads.seat_vertical_load_n:.0f} N "
        f"รวมถึงภาระแรงกระทำร่วมและผลกระทบจากการใช้งาน เพื่อป้องกันความเสียหายจากขีดจำกัดความเค้นคราก (Yield Stress), "
        f"การโก่งเดาะของเสารองรับ (Column Buckling) และการรับภาระล้าแบบวัฏจักร (Fatigue Life Endurance) ตลอดอายุการใช้งาน\n\n"
        f"โครงสร้างเลือกใช้วัสดุ {m.name} ที่มีคุณสมบัติความแข็งแรงผลผลิตสูง ทนทานต่อแรงกดอัดตามแนวแกนและโมเมนต์ดัดได้ดีเยี่ยม "
        f"ประกอบด้วยชิ้นส่วนโครงสร้างหลักจำนวน {len(component_names)} ชิ้นส่วน ได้แก่ {', '.join(component_names)} "
        f"ซึ่งได้รับการคำนวณและตรวจสอบความแข็งแรงอย่างละเอียดตามขั้นตอนวิศวกรรมในรายงานฉบับนี้"
    )

    comps = {
        "columns": f"ทำหน้าที่ถ่ายทอดน้ำหนักบรรทุกแนวดิ่งทั้งหมดลงสู่พื้นผิวสัมผัส จัดวางจำนวน {g.num_legs} เสาเพื่อกระจายแรงอย่างสมดุล และป้องกันความล้มเหลวจากการโก่งเดาะ (Buckling) ภายใต้ภาระกดอัดตามแนวแกน",
        "seat_rails": "ทำหน้าที่รองรับแรงกดกระจายตัวสม่ำเสมอด้านบนและส่งถ่ายแรงไปยังหัวเสารองรับ โดยทำงานในลักษณะคานช่วงเดียวรับโมเมนต์ดัดและแรงเฉือน",
        "stretchers": "ทำหน้าที่ยึดตรึงระหว่างเสาโครงสร้างเพื่อลดความยาวประสิทธิผลของเสา เพิ่มเสถียรภาพการรับแรง และรองรับแรงกระแทกบริเวณฐานล่าง",
        "armrests": "ทำหน้าที่รองรับแรงกดแนวดิ่งและแรงผลักด้านข้างจากแขนผู้ใช้งาน พฤติกรรมโครงสร้างเป็นคานยื่นรับโมเมนต์ดัดร่วมกับแรงเฉือน",
    }
    return {"introduction": intro, "components": comps}
