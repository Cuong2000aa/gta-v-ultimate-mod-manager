/*
 * NCCVision Ultimate cinematic grade (depth-free).
 *
 * Color-only stack aiming for a richer “premium ReShade” look without ENB /
 * depth effects: filmic curve, teal/orange split, soft highlight bloom from
 * neighbor samples, mild local contrast, and a gentle vignette. Safe for
 * GTA V pause menus.
 */

#include "ReShade.fxh"
#include "ReShadeUI.fxh"

uniform float Exposure < __UNIFORM_DRAG_FLOAT1
    ui_min = -0.50; ui_max = 0.50; ui_step = 0.01;
    ui_label = "Exposure";
> = 0.02;

uniform float Contrast < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.80; ui_max = 1.35; ui_step = 0.01;
    ui_label = "Contrast";
> = 1.05;

uniform float Saturation < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.70; ui_max = 1.50; ui_step = 0.01;
    ui_label = "Saturation";
> = 1.08;

uniform float HighlightCompression < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.00; ui_max = 1.00; ui_step = 0.01;
    ui_label = "Highlight protection";
> = 0.36;

uniform float ShadowLift < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.00; ui_max = 0.10; ui_step = 0.001;
    ui_label = "Shadow detail";
> = 0.022;

uniform float TealShadows < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.00; ui_max = 0.14; ui_step = 0.001;
    ui_label = "Teal shadows";
> = 0.018;

uniform float WarmHighlights < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.00; ui_max = 0.14; ui_step = 0.001;
    ui_label = "Warm highlights";
> = 0.028;

uniform float SoftBloom < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.00; ui_max = 0.35; ui_step = 0.01;
    ui_label = "Soft highlight bloom";
> = 0.08;

uniform float LocalContrast < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.00; ui_max = 0.40; ui_step = 0.01;
    ui_label = "Local contrast";
> = 0.24;

uniform float Vignette < __UNIFORM_DRAG_FLOAT1
    ui_min = 0.00; ui_max = 0.35; ui_step = 0.01;
    ui_label = "Vignette";
> = 0.06;

float3 SoftBloomSample(float2 texcoord)
{
    float2 px = float2(BUFFER_RCP_WIDTH, BUFFER_RCP_HEIGHT) * 2.25;
    float3 acc = tex2D(ReShade::BackBuffer, texcoord).rgb * 0.28;
    acc += tex2D(ReShade::BackBuffer, texcoord + float2( px.x, 0.0)).rgb * 0.12;
    acc += tex2D(ReShade::BackBuffer, texcoord + float2(-px.x, 0.0)).rgb * 0.12;
    acc += tex2D(ReShade::BackBuffer, texcoord + float2(0.0,  px.y)).rgb * 0.12;
    acc += tex2D(ReShade::BackBuffer, texcoord + float2(0.0, -px.y)).rgb * 0.12;
    acc += tex2D(ReShade::BackBuffer, texcoord + float2( px.x,  px.y)).rgb * 0.08;
    acc += tex2D(ReShade::BackBuffer, texcoord + float2(-px.x,  px.y)).rgb * 0.08;
    acc += tex2D(ReShade::BackBuffer, texcoord + float2( px.x, -px.y)).rgb * 0.08;
    acc += tex2D(ReShade::BackBuffer, texcoord + float2(-px.x, -px.y)).rgb * 0.08;
    return saturate(acc);
}

float FilmicCurve(float x)
{
    // Gentle S-curve: lift mids, protect extremes without crushing blacks.
    float a = saturate(x);
    return saturate(a * a * (3.0 - 2.0 * a) * 0.55 + a * 0.45);
}

float3 NCCCinematicPass(
    float4 position : SV_Position,
    float2 texcoord : TexCoord
) : SV_Target
{
    float3 color = saturate(tex2D(ReShade::BackBuffer, texcoord).rgb);
    float3 bloom_src = SoftBloomSample(texcoord);
    color *= exp2(Exposure);

    float luma = dot(color, float3(0.2126, 0.7152, 0.0722));
    color += ShadowLift * (1.0 - luma) * (1.0 - luma);

    float blend = smoothstep(0.18, 0.82, luma);
    float3 shadow_tint = float3(1.0 - TealShadows, 1.0 + TealShadows * 0.15, 1.0 + TealShadows);
    float3 highlight_tint = float3(
        1.0 + WarmHighlights,
        1.0 + WarmHighlights * 0.30,
        1.0 - WarmHighlights * 0.35
    );
    color *= lerp(shadow_tint, highlight_tint, blend);

    // Soft highlight bloom (screen-space neighbors only — no depth).
    float3 bloom = max(bloom_src - 0.55, 0.0);
    bloom *= bloom;
    color += bloom * SoftBloom * 1.8;

    // Local micro-contrast for walls, props, foliage — not roads only.
    float2 detail_px = float2(BUFFER_RCP_WIDTH, BUFFER_RCP_HEIGHT) * 1.15;
    float3 near_blur =
        tex2D(ReShade::BackBuffer, texcoord).rgb * 0.40 +
        tex2D(ReShade::BackBuffer, texcoord + float2( detail_px.x, 0.0)).rgb * 0.15 +
        tex2D(ReShade::BackBuffer, texcoord + float2(-detail_px.x, 0.0)).rgb * 0.15 +
        tex2D(ReShade::BackBuffer, texcoord + float2(0.0,  detail_px.y)).rgb * 0.15 +
        tex2D(ReShade::BackBuffer, texcoord + float2(0.0, -detail_px.y)).rgb * 0.15;
    color = lerp(color, color + (color - near_blur), LocalContrast);

    color = (color - 0.5) * Contrast + 0.5;
    color.r = FilmicCurve(color.r);
    color.g = FilmicCurve(color.g);
    color.b = FilmicCurve(color.b);

    float3 highlight = max(color - 0.62, 0.0);
    color = min(color, 0.62) + highlight /
        (1.0 + HighlightCompression * highlight * 4.2);

    luma = dot(color, float3(0.2126, 0.7152, 0.0722));
    color = lerp(luma.xxx, color, Saturation);

    float2 uv = texcoord * 2.0 - 1.0;
    float vig = saturate(1.0 - dot(uv, uv) * Vignette);
    color *= lerp(1.0 - Vignette * 0.55, 1.0, vig);

    return saturate(color);
}

technique NCCCinematic
{
    pass
    {
        VertexShader = PostProcessVS;
        PixelShader = NCCCinematicPass;
    }
}
