/*
 * CuongVision Ultimate cinematic grade.
 *
 * One color-only pass: highlight protection, rich saturation and restrained
 * teal/orange separation. It never samples depth and is safe for GTA V menus.
 */

#include "ReShade.fxh"
#include "ReShadeUI.fxh"

uniform float Exposure < __UNIFORM_DRAG_FLOAT1
    ui_min = -0.50; ui_max = 0.50; ui_step = 0.01;
    ui_label = "Exposure";
> = -0.04;

uniform float Contrast < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.80; ui_max = 1.30; ui_step = 0.01;
    ui_label = "Contrast";
> = 1.08;

uniform float Saturation < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.70; ui_max = 1.40; ui_step = 0.01;
    ui_label = "Saturation";
> = 1.14;

uniform float HighlightCompression < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.00; ui_max = 1.00; ui_step = 0.01;
    ui_label = "Highlight protection";
> = 0.35;

uniform float ShadowLift < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.00; ui_max = 0.08; ui_step = 0.001;
    ui_label = "Shadow detail";
> = 0.012;

uniform float TealShadows < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.00; ui_max = 0.10; ui_step = 0.001;
    ui_label = "Teal shadows";
> = 0.022;

uniform float WarmHighlights < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.00; ui_max = 0.10; ui_step = 0.001;
    ui_label = "Warm highlights";
> = 0.035;

float3 CuongCinematicPass(
    float4 position : SV_Position,
    float2 texcoord : TexCoord
) : SV_Target
{
    float3 color = saturate(tex2D(ReShade::BackBuffer, texcoord).rgb);
    color *= exp2(Exposure);

    float luma = dot(color, float3(0.2126, 0.7152, 0.0722));
    color += ShadowLift * (1.0 - luma) * (1.0 - luma);

    float blend = smoothstep(0.22, 0.78, luma);
    float3 shadow_tint = float3(1.0 - TealShadows, 1.0, 1.0 + TealShadows);
    float3 highlight_tint = float3(
        1.0 + WarmHighlights,
        1.0 + WarmHighlights * 0.25,
        1.0 - WarmHighlights * 0.30
    );
    color *= lerp(shadow_tint, highlight_tint, blend);

    color = (color - 0.5) * Contrast + 0.5;

    float3 highlight = max(color - 0.65, 0.0);
    color = min(color, 0.65) + highlight /
        (1.0 + HighlightCompression * highlight * 4.0);

    luma = dot(color, float3(0.2126, 0.7152, 0.0722));
    color = lerp(luma.xxx, color, Saturation);
    return saturate(color);
}

technique CuongCinematic
{
    pass
    {
        VertexShader = PostProcessVS;
        PixelShader = CuongCinematicPass;
    }
}
