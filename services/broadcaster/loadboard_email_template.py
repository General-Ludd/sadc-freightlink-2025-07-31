def daily_loadboard_template() -> str:

    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">

<title>SADC FREIGHTLINK | Daily Loadboard</title>

<style>
/* Mobile Responsive */
@media only screen and (max-width:600px){

.wrapper{
    width:100% !important;
}

.padding{
    padding:30px 24px !important;
}

.hero-title{
    font-size:30px !important;
    line-height:38px !important;
}

.hero-text{
    font-size:16px !important;
    line-height:28px !important;
}

.button{
    display:block !important;
    width:100% !important;
    box-sizing:border-box;
}

.logo{
    width:170px !important;
}

.stack{
    display:block !important;
    width:100% !important;
}

.stack td{
    display:block !important;
    width:100% !important;
    padding-bottom:18px !important;
}

}
</style>

</head>

<body style="margin:0;padding:0;background:#f7f4ee;font-family:Arial,Helvetica,sans-serif;">

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f7f4ee;padding:30px 15px;">

<tr>
<td align="center">

<table role="presentation"
class="wrapper"
width="620"
cellpadding="0"
cellspacing="0"
style="
max-width:620px;
width:100%;
background:#ffffff;
border:1px solid #e9e4db;
border-radius:14px;
overflow:hidden;
">

<!-- Header -->

<tr>

<td align="center"
style="
padding:35px 25px;
background:#ffffff;
">

<img
class="logo"
src="https://ik.imagekit.io/0bf9ktdig/ChatGPT%20Image%20Sep%202,%202025,%2009_25_07%20PM.png?updatedAt=1762145054656"
alt="SADC Freightlink"
width="210"
style="display:block;border:0;max-width:210px;width:100%;height:auto;">

</td>

</tr>

<!-- Hero -->

<tr>

<td
class="padding"
style="
padding:48px;
background:#f5f1e8;
text-align:center;
">

<div style="
font-size:42px;
margin-bottom:18px;
">
🚛
</div>

<h1
class="hero-title"
style="
margin:0;
font-size:38px;
line-height:46px;
color:#111111;
font-weight:700;
">

Today's Freight Opportunities

</h1>

<p
class="hero-text"
style="
margin:20px 0 34px;
font-size:18px;
line-height:30px;
color:#555555;
">

New ad-hoc transport requirements have been published to the
<strong>SADC FREIGHTLINK Loadboard.</strong>

Secure available loads before they are allocated.

</p>

<a
href="https://sadcfreightlink.com/public-ftl-loadboard"
class="button"
style="
display:inline-block;
background:#111111;
color:#ffffff;
padding:16px 38px;
border-radius:8px;
font-size:16px;
font-weight:bold;
text-decoration:none;
letter-spacing:.4px;
">

VIEW TODAY'S LOADBOARD

</a>

</td>

</tr>

<!-- Features -->

<tr>

<td class="padding" style="padding:38px 42px;">

<table role="presentation" width="100%" class="stack">

<tr>

<td align="center">

<div style="font-size:32px;">📦</div>

<div style="
font-weight:bold;
font-size:16px;
color:#111111;
margin-top:10px;
">
Daily Spot Loads
</div>

<div style="
margin-top:8px;
font-size:14px;
line-height:24px;
color:#666666;
">
Fresh opportunities published every morning.
</div>

</td>

<td align="center">

<div style="font-size:32px;">🚚</div>

<div style="
font-weight:bold;
font-size:16px;
color:#111111;
margin-top:10px;
">
Nationwide Coverage
</div>

<div style="
margin-top:8px;
font-size:14px;
line-height:24px;
color:#666666;
">
South Africa & SADC freight movements.
</div>

</td>

<td align="center">

<div style="font-size:32px;">⚡</div>

<div style="
font-weight:bold;
font-size:16px;
color:#111111;
margin-top:10px;
">
Fast Booking
</div>

<div style="
margin-top:8px;
font-size:14px;
line-height:24px;
color:#666666;
">
Apply online in minutes.
</div>

</td>

</tr>

</table>

</td>

</tr>

<!-- Divider -->

<tr>

<td style="padding:0 42px;">

<hr style="
border:none;
border-top:1px solid #e5dfd5;
margin:0;
">

</td>

</tr>

<!-- Bottom CTA -->

<tr>

<td
class="padding"
style="
padding:38px 42px;
text-align:center;
">

<p style="
margin:0 0 28px;
font-size:16px;
line-height:28px;
color:#555555;
">

The highest number of available loads are typically published during the morning.
Checking early increases your chances of securing work.

</p>

<a
href="https://sadcfreightlink.com/public-ftl-loadboard"
class="button"
style="
display:inline-block;
background:#111111;
color:#ffffff;
padding:15px 34px;
border-radius:8px;
text-decoration:none;
font-weight:bold;
font-size:15px;
">

Browse Available Loads

</a>

</td>

</tr>

<!-- Footer -->

<tr>

<td
style="
background:#111111;
padding:32px 24px;
text-align:center;
">

<p style="
margin:0;
font-size:15px;
font-weight:bold;
color:#ffffff;
letter-spacing:.5px;
">

SADC FREIGHTLINK

</p>

<p style="
margin:12px 0 0;
font-size:13px;
line-height:24px;
color:#b8b8b8;
">

Managed Transport Execution for Southern Africa

</p>

<p style="
margin:18px 0 0;
font-size:12px;
line-height:22px;
color:#8d8d8d;
">

© 2026 SADC FREIGHTLINK. All Rights Reserved.

</p>

</td>

</tr>

</table>

</td>
</tr>

</table>

</body>
</html>
"""