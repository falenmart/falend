-- ShopClient (LocalScript)
-- Konum: StarterPlayer > StarterPlayerScripts > ShopClient
--
-- Mağaza arayüzünü tamamen kodla oluşturur; Studio'da elle UI kurmana gerek yok.
-- Renkleri THEME tablosundan, eşyaları ReplicatedStorage.ShopItems'tan değiştirebilirsin.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")
local MarketplaceService = game:GetService("MarketplaceService")

local player = Players.LocalPlayer
local ShopItems = require(ReplicatedStorage:WaitForChild("ShopItems"))
local Settings = ShopItems.Settings
local Remotes = ReplicatedStorage:WaitForChild("ShopRemotes")

local THEME = {
	Panel = Color3.fromRGB(20, 24, 38),
	Header = Color3.fromRGB(28, 34, 54),
	Sidebar = Color3.fromRGB(24, 29, 46),
	Card = Color3.fromRGB(34, 40, 66),
	CardSelected = Color3.fromRGB(43, 50, 84),
	Tab = Color3.fromRGB(32, 38, 60),
	Input = Color3.fromRGB(14, 17, 32),
	Border = Color3.fromRGB(46, 54, 87),
	Text = Color3.new(1, 1, 1),
	Muted = Color3.fromRGB(154, 163, 192),
	Accent = Color3.fromRGB(255, 200, 61),
	Gold = Color3.fromRGB(255, 213, 74),
	Backdrop = Color3.fromRGB(5, 8, 28),
}

local FONT = {
	Black = Enum.Font.GothamBlack,
	Bold = Enum.Font.GothamBold,
	Medium = Enum.Font.GothamMedium,
}

-- { üst renk, alt renk, gölge rengi, yazı rengi }
local STYLES = {
	Green = { Color3.fromRGB(61, 220, 132), Color3.fromRGB(34, 181, 102), Color3.fromRGB(22, 138, 75), THEME.Text },
	Blue = { Color3.fromRGB(77, 163, 255), Color3.fromRGB(47, 127, 214), Color3.fromRGB(31, 94, 163), THEME.Text },
	Gray = { Color3.fromRGB(53, 61, 94), Color3.fromRGB(53, 61, 94), Color3.fromRGB(35, 40, 63), THEME.Muted },
	Red = { Color3.fromRGB(255, 77, 94), Color3.fromRGB(235, 60, 78), Color3.fromRGB(176, 34, 50), THEME.Text },
	Gold = { Color3.fromRGB(255, 216, 92), Color3.fromRGB(255, 176, 32), Color3.fromRGB(185, 118, 11), Color3.fromRGB(74, 44, 0) },
}

local BASE_SIZE = Vector2.new(860, 540)
local COIN = Settings.CoinIcon

----------------------------------------------------------------------
-- Yardımcılar
----------------------------------------------------------------------

local function create(className, props, children)
	local inst = Instance.new(className)
	local parent
	for key, value in pairs(props or {}) do
		if key == "Parent" then
			parent = value
		else
			inst[key] = value
		end
	end
	for _, child in ipairs(children or {}) do
		child.Parent = inst
	end
	if parent then
		inst.Parent = parent
	end
	return inst
end

local function corner(radius)
	return create("UICorner", { CornerRadius = UDim.new(0, radius) })
end

local function stroke(color, thickness, transparency)
	return create("UIStroke", {
		Color = color,
		Thickness = thickness,
		Transparency = transparency or 0,
		ApplyStrokeMode = Enum.ApplyStrokeMode.Border,
	})
end

local function padding(top, right, bottom, left)
	return create("UIPadding", {
		PaddingTop = UDim.new(0, top),
		PaddingRight = UDim.new(0, right or top),
		PaddingBottom = UDim.new(0, bottom or top),
		PaddingLeft = UDim.new(0, left or right or top),
	})
end

local function text(props)
	local merged = {
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		Font = FONT.Bold,
		TextColor3 = THEME.Text,
		TextSize = 14,
	}
	for key, value in pairs(props) do
		merged[key] = value
	end
	return create("TextLabel", merged)
end

local function tween(inst, time, goal, style, direction)
	local t = TweenService:Create(inst, TweenInfo.new(time, style or Enum.EasingStyle.Quad, direction or Enum.EasingDirection.Out), goal)
	t:Play()
	return t
end

local function formatNumber(n)
	local s = tostring(math.floor(n))
	local formatted = s:reverse():gsub("(%d%d%d)", "%1."):reverse()
	return (formatted:gsub("^%.", ""))
end

-- Rengi koyulaştır / açıklaştır gibi küçük karışımlar için
local function mix(a, b, t)
	return a:Lerp(b, t)
end

-- Emoji ya da (Image verilmişse) resim gösteren ikon
local function iconView(item, size, textSize)
	if item.Image then
		return create("ImageLabel", {
			BackgroundTransparency = 1,
			Size = size,
			Image = item.Image,
			ScaleType = Enum.ScaleType.Fit,
		})
	end
	return text({ Size = size, Text = item.Icon, TextSize = textSize })
end

-- Altında gölgesi olan, basınca içeri giren "3D" buton
local function button3D(props)
	local depth = props.Depth or 4
	local radius = props.Radius or 12

	local holder = create("Frame", {
		Name = props.Name or "Button",
		Size = props.Size,
		Position = props.Position or UDim2.new(),
		AnchorPoint = props.AnchorPoint or Vector2.zero,
		LayoutOrder = props.LayoutOrder or 0,
		BorderSizePixel = 0,
		Parent = props.Parent,
	}, { corner(radius) })

	local face = create("TextButton", {
		Name = "Face",
		AutoButtonColor = false,
		Size = UDim2.new(1, 0, 1, -depth),
		BackgroundColor3 = Color3.new(1, 1, 1),
		BorderSizePixel = 0,
		Font = FONT.Black,
		TextSize = props.TextSize or 16,
		Text = props.Text or "",
		Parent = holder,
	}, { corner(radius) })
	local gradient = create("UIGradient", { Rotation = 90, Parent = face })

	local obj = { Holder = holder, Face = face, Activated = face.Activated }

	function obj:SetStyle(name)
		local s = STYLES[name]
		gradient.Color = ColorSequence.new(s[1], s[2])
		holder.BackgroundColor3 = s[3]
		face.TextColor3 = s[4]
	end

	function obj:SetText(value)
		face.Text = value
	end

	local function release()
		face.Position = UDim2.new()
	end
	face.InputBegan:Connect(function(input)
		if input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then
			face.Position = UDim2.fromOffset(0, depth - 1)
		end
	end)
	face.InputEnded:Connect(release)
	face.MouseLeave:Connect(release)

	obj:SetStyle(props.Style or "Green")
	return obj
end

-- Yuvarlatılmış panelde, alttaki parçaların köşeleri taşmasın diye
-- sadece istenen köşeyi yuvarlak bırakan dolgu frame'leri ekler.
local function roundOnly(frame, radius, cornerName)
	corner(radius).Parent = frame
	local fills = {
		BottomLeft = { { UDim2.new(1, 0, 0, radius), UDim2.new(0, 0, 0, 0) }, { UDim2.new(0, radius, 1, 0), UDim2.new(1, -radius, 0, 0) } },
		BottomRight = { { UDim2.new(1, 0, 0, radius), UDim2.new(0, 0, 0, 0) }, { UDim2.new(0, radius, 1, 0), UDim2.new(0, 0, 0, 0) } },
		Top = { { UDim2.new(1, 0, 0, radius), UDim2.new(0, 0, 1, -radius) } },
	}
	for _, fill in ipairs(fills[cornerName]) do
		create("Frame", {
			Name = "CornerFill",
			Size = fill[1],
			Position = fill[2],
			BackgroundColor3 = frame.BackgroundColor3,
			BorderSizePixel = 0,
			ZIndex = frame.ZIndex,
			Parent = frame,
		})
	end
end

----------------------------------------------------------------------
-- Durum
----------------------------------------------------------------------

local state = {
	Category = ShopItems.Categories[1].Id,
	Selected = nil,
	Owned = {},
	Equipped = {},
	Search = "",
	Open = false,
	Busy = false,
	Coins = 0,
}

local cards = {} -- [itemId] = { Root, Stroke, Price }
local tabs = {} -- [categoryId] = { Face, Holder }
local baseScale = 1

----------------------------------------------------------------------
-- Arayüz
----------------------------------------------------------------------

local screenGui = create("ScreenGui", {
	Name = "ShopGui",
	ResetOnSpawn = false,
	IgnoreGuiInset = true,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	Parent = player:WaitForChild("PlayerGui"),
})

-- HUD: sol taraftaki coin göstergesi ve mağaza butonu
local hud = create("Frame", {
	Name = "Hud",
	AnchorPoint = Vector2.new(0, 0.5),
	Position = UDim2.new(0, 24, 0.5, 0),
	Size = UDim2.fromOffset(160, 140),
	BackgroundTransparency = 1,
	Parent = screenGui,
})
local hudScale = create("UIScale", { Parent = hud })

local hudCoins = create("Frame", {
	Name = "Coins",
	AutomaticSize = Enum.AutomaticSize.X,
	Size = UDim2.fromOffset(0, 40),
	BackgroundColor3 = THEME.Panel,
	BackgroundTransparency = 0.1,
	Parent = hud,
}, {
	corner(20),
	stroke(Color3.new(1, 1, 1), 2, 0.87),
	padding(0, 16, 0, 10),
	create("UIListLayout", {
		FillDirection = Enum.FillDirection.Horizontal,
		VerticalAlignment = Enum.VerticalAlignment.Center,
		SortOrder = Enum.SortOrder.LayoutOrder,
		Padding = UDim.new(0, 8),
	}),
	text({ Size = UDim2.fromOffset(24, 24), Text = COIN, TextSize = 20 }),
})
local hudCoinLabel = text({
	Name = "Amount",
	AutomaticSize = Enum.AutomaticSize.X,
	Size = UDim2.fromOffset(0, 40),
	Font = FONT.Black,
	TextSize = 20,
	Text = "0",
	LayoutOrder = 1,
	Parent = hudCoins,
})

local hudButton = button3D({
	Name = "ShopButton",
	Position = UDim2.fromOffset(0, 54),
	Size = UDim2.fromOffset(76, 82),
	Radius = 18,
	Depth = 6,
	Style = "Gold",
	Parent = hud,
})
stroke(Color3.new(1, 1, 1), 3, 0.8).Parent = hudButton.Face
text({ Size = UDim2.new(1, 0, 0, 44), Position = UDim2.fromOffset(0, 8), Text = "🛒", TextSize = 30, Parent = hudButton.Face })
text({
	Size = UDim2.new(1, 0, 0, 16),
	Position = UDim2.new(0, 0, 1, -24),
	Text = "MAĞAZA",
	Font = FONT.Black,
	TextSize = 12,
	TextColor3 = STYLES.Gold[4],
	Parent = hudButton.Face,
})

-- Arka plan karartma
local backdrop = create("TextButton", {
	Name = "Backdrop",
	Text = "",
	AutoButtonColor = false,
	Size = UDim2.fromScale(1, 1),
	BackgroundColor3 = THEME.Backdrop,
	BackgroundTransparency = 1,
	Visible = false,
	ZIndex = 5,
	Parent = screenGui,
})

-- Ana panel
local main = create("Frame", {
	Name = "Shop",
	AnchorPoint = Vector2.new(0.5, 0.5),
	Position = UDim2.fromScale(0.5, 0.5),
	Size = UDim2.fromOffset(BASE_SIZE.X, BASE_SIZE.Y),
	BackgroundColor3 = THEME.Panel,
	Visible = false,
	ZIndex = 10,
	Parent = screenGui,
}, { corner(18), stroke(THEME.Border, 3) })
local mainScale = create("UIScale", { Parent = main })

-- Header
local header = create("Frame", {
	Name = "Header",
	Size = UDim2.new(1, 0, 0, 68),
	BackgroundColor3 = THEME.Header,
	BorderSizePixel = 0,
	ZIndex = 10,
	Parent = main,
})
roundOnly(header, 18, "Top")
create("Frame", {
	Name = "Line",
	Size = UDim2.new(1, 0, 0, 2),
	Position = UDim2.new(0, 0, 1, 0),
	BackgroundColor3 = THEME.Border,
	BorderSizePixel = 0,
	ZIndex = 11,
	Parent = header,
})
text({ Position = UDim2.fromOffset(22, 0), Size = UDim2.fromOffset(36, 68), Text = "🛒", TextSize = 26, ZIndex = 11, Parent = header })
text({
	Position = UDim2.fromOffset(64, 0),
	Size = UDim2.fromOffset(240, 68),
	Text = "MAĞAZA",
	Font = FONT.Black,
	TextSize = 28,
	TextXAlignment = Enum.TextXAlignment.Left,
	ZIndex = 11,
	Parent = header,
})

local coinPill = create("Frame", {
	Name = "Coins",
	AnchorPoint = Vector2.new(1, 0.5),
	Position = UDim2.new(1, -76, 0.5, 0),
	AutomaticSize = Enum.AutomaticSize.X,
	Size = UDim2.fromOffset(0, 42),
	BackgroundColor3 = THEME.Input,
	ZIndex = 11,
	Parent = header,
}, {
	corner(21),
	stroke(THEME.Gold, 2, 0.67),
	padding(0, 8, 0, 10),
	create("UIListLayout", {
		FillDirection = Enum.FillDirection.Horizontal,
		VerticalAlignment = Enum.VerticalAlignment.Center,
		SortOrder = Enum.SortOrder.LayoutOrder,
		Padding = UDim.new(0, 8),
	}),
	text({ Size = UDim2.fromOffset(26, 26), Text = COIN, TextSize = 22, ZIndex = 12 }),
})
local headerCoinLabel = text({
	Name = "Amount",
	AutomaticSize = Enum.AutomaticSize.X,
	Size = UDim2.fromOffset(0, 42),
	Font = FONT.Black,
	TextSize = 20,
	TextColor3 = THEME.Gold,
	Text = "0",
	LayoutOrder = 1,
	ZIndex = 12,
	Parent = coinPill,
})
local plusButton = create("TextButton", {
	Name = "Plus",
	Size = UDim2.fromOffset(26, 26),
	BackgroundColor3 = STYLES.Green[1],
	Text = "+",
	Font = FONT.Black,
	TextSize = 20,
	TextColor3 = Color3.fromRGB(11, 58, 32),
	AutoButtonColor = true,
	LayoutOrder = 2,
	ZIndex = 12,
	Parent = coinPill,
}, { corner(13) })

local closeButton = button3D({
	Name = "Close",
	AnchorPoint = Vector2.new(1, 0.5),
	Position = UDim2.new(1, -16, 0.5, 0),
	Size = UDim2.fromOffset(44, 48),
	Text = "✕",
	TextSize = 22,
	Style = "Red",
	Parent = header,
})
closeButton.Holder.ZIndex = 11
closeButton.Face.ZIndex = 12

-- Gövde
local body = create("Frame", {
	Name = "Body",
	Position = UDim2.fromOffset(0, 70),
	Size = UDim2.new(1, 0, 1, -70),
	BackgroundTransparency = 1,
	ZIndex = 10,
	Parent = main,
})

-- Sol menü (kategoriler)
local sidebar = create("Frame", {
	Name = "Sidebar",
	Size = UDim2.new(0, 178, 1, 0),
	BackgroundColor3 = THEME.Sidebar,
	BorderSizePixel = 0,
	ZIndex = 10,
	Parent = body,
})
roundOnly(sidebar, 18, "BottomLeft")
local tabList = create("Frame", {
	Name = "Tabs",
	Size = UDim2.fromScale(1, 1),
	BackgroundTransparency = 1,
	ZIndex = 11,
	Parent = sidebar,
}, {
	padding(14, 12),
	create("UIListLayout", { Padding = UDim.new(0, 8), SortOrder = Enum.SortOrder.LayoutOrder }),
})

-- Orta kısım (arama + eşya ızgarası)
local gridArea = create("Frame", {
	Name = "GridArea",
	Position = UDim2.fromOffset(178, 0),
	Size = UDim2.new(1, -178 - 236, 1, 0),
	BackgroundTransparency = 1,
	ZIndex = 10,
	Parent = body,
}, { padding(14) })

local searchBox = create("TextBox", {
	Name = "Search",
	Size = UDim2.new(1, 0, 0, 38),
	BackgroundColor3 = THEME.Input,
	PlaceholderText = "🔍 Eşya ara...",
	PlaceholderColor3 = THEME.Muted,
	Text = "",
	ClearTextOnFocus = false,
	Font = FONT.Medium,
	TextSize = 14,
	TextColor3 = THEME.Text,
	TextXAlignment = Enum.TextXAlignment.Left,
	ZIndex = 11,
	Parent = gridArea,
}, { corner(10), stroke(THEME.Border, 2), padding(0, 12) })

local scroll = create("ScrollingFrame", {
	Name = "Items",
	Position = UDim2.fromOffset(0, 50),
	Size = UDim2.new(1, 0, 1, -50),
	BackgroundTransparency = 1,
	BorderSizePixel = 0,
	ScrollBarThickness = 6,
	ScrollBarImageColor3 = Color3.new(1, 1, 1),
	ScrollBarImageTransparency = 0.85,
	ScrollingDirection = Enum.ScrollingDirection.Y,
	AutomaticCanvasSize = Enum.AutomaticSize.Y,
	CanvasSize = UDim2.new(),
	ZIndex = 11,
	Parent = gridArea,
}, {
	padding(3, 3, 3, 3),
	create("UIGridLayout", {
		CellSize = UDim2.fromOffset(127, 186),
		CellPadding = UDim2.fromOffset(12, 12),
		SortOrder = Enum.SortOrder.LayoutOrder,
	}),
})

local emptyLabel = text({
	Size = UDim2.new(1, 0, 0, 40),
	Position = UDim2.fromOffset(0, 70),
	Text = "Eşya bulunamadı 😕",
	TextColor3 = THEME.Muted,
	Visible = false,
	ZIndex = 12,
	Parent = gridArea,
})

-- Sağ panel (detaylar)
local detail = create("Frame", {
	Name = "Detail",
	AnchorPoint = Vector2.new(1, 0),
	Position = UDim2.fromScale(1, 0),
	Size = UDim2.new(0, 236, 1, 0),
	BackgroundColor3 = THEME.Sidebar,
	BorderSizePixel = 0,
	ZIndex = 10,
	Parent = body,
})
roundOnly(detail, 18, "BottomRight")
create("Frame", {
	Name = "Line",
	Size = UDim2.new(0, 2, 1, 0),
	BackgroundColor3 = Color3.fromRGB(35, 42, 68),
	BorderSizePixel = 0,
	ZIndex = 11,
	Parent = detail,
})
local detailContent = create("Frame", {
	Name = "Content",
	Size = UDim2.fromScale(1, 1),
	BackgroundTransparency = 1,
	ZIndex = 11,
	Parent = detail,
}, { padding(16) })

local bigIcon = create("Frame", {
	Name = "Icon",
	Size = UDim2.new(1, 0, 0, 150),
	BackgroundColor3 = Color3.new(1, 1, 1),
	ZIndex = 11,
	Parent = detailContent,
}, { corner(14) })
local bigIconStroke = stroke(THEME.Border, 2, 0.4)
bigIconStroke.Parent = bigIcon
local bigIconGradient = create("UIGradient", { Rotation = 90, Parent = bigIcon })

local detailName = text({
	Position = UDim2.fromOffset(0, 160),
	Size = UDim2.new(1, 0, 0, 28),
	Font = FONT.Black,
	TextSize = 21,
	TextXAlignment = Enum.TextXAlignment.Left,
	TextTruncate = Enum.TextTruncate.AtEnd,
	ZIndex = 11,
	Parent = detailContent,
})
local rarityPill = text({
	Position = UDim2.fromOffset(0, 192),
	AutomaticSize = Enum.AutomaticSize.X,
	Size = UDim2.fromOffset(0, 20),
	BackgroundTransparency = 0,
	Font = FONT.Black,
	TextSize = 11,
	TextColor3 = Color3.fromRGB(36, 21, 0),
	ZIndex = 11,
	Parent = detailContent,
})
corner(10).Parent = rarityPill
padding(0, 10).Parent = rarityPill

local detailDesc = text({
	Position = UDim2.fromOffset(0, 220),
	Size = UDim2.new(1, 0, 0, 58),
	Font = FONT.Medium,
	TextSize = 13,
	TextColor3 = THEME.Muted,
	TextWrapped = true,
	TextXAlignment = Enum.TextXAlignment.Left,
	TextYAlignment = Enum.TextYAlignment.Top,
	ZIndex = 11,
	Parent = detailContent,
})
local statsFrame = create("Frame", {
	Position = UDim2.fromOffset(0, 284),
	Size = UDim2.new(1, 0, 0, 70),
	BackgroundTransparency = 1,
	ZIndex = 11,
	Parent = detailContent,
}, { create("UIListLayout", { Padding = UDim.new(0, 6), SortOrder = Enum.SortOrder.LayoutOrder }) })

local detailButton = button3D({
	Name = "Action",
	AnchorPoint = Vector2.new(0, 1),
	Position = UDim2.fromScale(0, 1),
	Size = UDim2.new(1, 0, 0, 56),
	Depth = 5,
	TextSize = 18,
	Parent = detailContent,
})
detailButton.Holder.ZIndex = 11
detailButton.Face.ZIndex = 12

-- Onay penceresi
local modal = create("Frame", {
	Name = "Confirm",
	AnchorPoint = Vector2.new(0.5, 0.5),
	Position = UDim2.fromScale(0.5, 0.5),
	Size = UDim2.fromOffset(400, 318),
	BackgroundColor3 = THEME.Panel,
	Visible = false,
	ZIndex = 30,
	Parent = screenGui,
}, { corner(18), stroke(THEME.Border, 3), padding(22) })
local modalScale = create("UIScale", { Parent = modal })
local modalDim = create("TextButton", {
	Name = "ModalDim",
	Text = "",
	AutoButtonColor = false,
	Size = UDim2.fromScale(1, 1),
	BackgroundColor3 = THEME.Backdrop,
	BackgroundTransparency = 0.2,
	Visible = false,
	ZIndex = 29,
	Parent = screenGui,
})
local modalIconHolder = create("Frame", {
	Size = UDim2.new(1, 0, 0, 74),
	BackgroundTransparency = 1,
	ZIndex = 31,
	Parent = modal,
})
local modalName = text({
	Position = UDim2.fromOffset(0, 84),
	Size = UDim2.new(1, 0, 0, 28),
	Font = FONT.Black,
	TextSize = 22,
	ZIndex = 31,
	Parent = modal,
})
text({
	Position = UDim2.fromOffset(0, 114),
	Size = UDim2.new(1, 0, 0, 20),
	Font = FONT.Medium,
	TextSize = 14,
	TextColor3 = THEME.Muted,
	Text = "Bu eşyayı satın almak istediğine emin misin?",
	ZIndex = 31,
	Parent = modal,
})
local modalCost = text({
	AnchorPoint = Vector2.new(0.5, 0),
	Position = UDim2.new(0.5, 0, 0, 146),
	AutomaticSize = Enum.AutomaticSize.X,
	Size = UDim2.fromOffset(0, 38),
	BackgroundTransparency = 0,
	BackgroundColor3 = THEME.Input,
	Font = FONT.Black,
	TextSize = 22,
	TextColor3 = THEME.Gold,
	ZIndex = 31,
	Parent = modal,
})
corner(19).Parent = modalCost
padding(0, 18).Parent = modalCost

local cancelButton = button3D({
	Name = "Cancel",
	AnchorPoint = Vector2.new(0, 1),
	Position = UDim2.fromScale(0, 1),
	Size = UDim2.new(0.5, -6, 0, 54),
	Text = "İPTAL",
	TextSize = 17,
	Style = "Gray",
	Parent = modal,
})
cancelButton.Face.TextColor3 = THEME.Text
local confirmButton = button3D({
	Name = "Confirm",
	AnchorPoint = Vector2.new(1, 1),
	Position = UDim2.fromScale(1, 1),
	Size = UDim2.new(0.5, -6, 0, 54),
	Text = "ONAYLA",
	TextSize = 17,
	Style = "Green",
	Parent = modal,
})
for _, b in ipairs({ cancelButton, confirmButton }) do
	b.Holder.ZIndex = 31
	b.Face.ZIndex = 32
end

-- Bildirim
local toast = text({
	Name = "Toast",
	AnchorPoint = Vector2.new(0.5, 1),
	Position = UDim2.new(0.5, 0, 0, -10),
	AutomaticSize = Enum.AutomaticSize.X,
	Size = UDim2.fromOffset(0, 48),
	BackgroundTransparency = 0,
	BackgroundColor3 = Color3.new(1, 1, 1),
	Font = FONT.Black,
	TextSize = 17,
	ZIndex = 50,
	Parent = screenGui,
})
corner(14).Parent = toast
padding(0, 22).Parent = toast
local toastGradient = create("UIGradient", { Rotation = 90, Parent = toast })
local toastScale = create("UIScale", { Parent = toast })

----------------------------------------------------------------------
-- Davranışlar
----------------------------------------------------------------------

local toastToken = 0
local function showToast(message, ok)
	toastToken += 1
	local token = toastToken
	local style = STYLES[ok and "Green" or "Red"]
	toastGradient.Color = ColorSequence.new(style[1], style[2])
	toast.Text = (ok and "✅ " or "⚠️ ") .. message
	toast.Position = UDim2.new(0.5, 0, 0, -10)
	tween(toast, 0.3, { Position = UDim2.new(0.5, 0, 0, 118) }, Enum.EasingStyle.Back)
	task.delay(2.4, function()
		if token == toastToken then
			tween(toast, 0.25, { Position = UDim2.new(0.5, 0, 0, -10) }, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
		end
	end)
end

local function setCoins(value)
	state.Coins = value
	local formatted = formatNumber(value)
	headerCoinLabel.Text = formatted
	hudCoinLabel.Text = formatted
end

local function priceText(item)
	return item.Price == 0 and "ÜCRETSİZ" or (COIN .. " " .. formatNumber(item.Price))
end

local function itemStatus(item)
	if state.Equipped[item.Category] == item.Id then
		return "Equipped"
	elseif state.Owned[item.Id] then
		return "Owned"
	end
	return "Locked"
end

local function updateCard(item)
	local card = cards[item.Id]
	if not card then
		return
	end
	local status = itemStatus(item)
	if status == "Equipped" then
		card.Price:SetStyle("Blue")
		card.Price:SetText("KUŞANILDI")
		card.Price.Face.TextSize = 13
	elseif status == "Owned" then
		card.Price:SetStyle("Gray")
		card.Price:SetText("SAHİPSİN")
		card.Price.Face.TextSize = 13
	else
		card.Price:SetStyle("Green")
		card.Price:SetText(priceText(item))
		card.Price.Face.TextSize = 16
	end
	local selected = state.Selected == item.Id
	card.Stroke.Enabled = selected
	card.Root.BackgroundColor3 = selected and THEME.CardSelected or THEME.Card
end

local detailHover = false
local function updateDetail()
	local item = ShopItems.ById[state.Selected]
	detailContent.Visible = item ~= nil
	if not item then
		return
	end
	local rarity = ShopItems.Rarities[item.Rarity]

	for _, child in ipairs(bigIcon:GetChildren()) do
		if child:IsA("GuiObject") then
			child:Destroy()
		end
	end
	local icon = iconView(item, UDim2.fromScale(1, 1), 86)
	icon.ZIndex = 12
	icon.Parent = bigIcon
	bigIconGradient.Color = ColorSequence.new({
		ColorSequenceKeypoint.new(0, mix(THEME.Tab, rarity.Color, 0.15)),
		ColorSequenceKeypoint.new(0.5, mix(THEME.Tab, rarity.Color, 0.45)),
		ColorSequenceKeypoint.new(1, mix(THEME.Tab, rarity.Color, 0.1)),
	})
	bigIconStroke.Color = rarity.Color

	detailName.Text = item.Name
	rarityPill.Text = rarity.Name:upper()
	rarityPill.BackgroundColor3 = rarity.Color
	detailDesc.Text = item.Description or ""

	for _, child in ipairs(statsFrame:GetChildren()) do
		if child:IsA("GuiObject") then
			child:Destroy()
		end
	end
	for i, stat in ipairs(item.Stats or {}) do
		local row = create("Frame", {
			Size = UDim2.new(1, 0, 0, 30),
			BackgroundColor3 = THEME.Tab,
			LayoutOrder = i,
			ZIndex = 11,
			Parent = statsFrame,
		}, { corner(8), padding(0, 10) })
		text({ Size = UDim2.fromScale(1, 1), Text = stat[1], TextSize = 13, TextXAlignment = Enum.TextXAlignment.Left, ZIndex = 12, Parent = row })
		text({ Size = UDim2.fromScale(1, 1), Text = stat[2], TextSize = 13, TextColor3 = THEME.Accent, TextXAlignment = Enum.TextXAlignment.Right, ZIndex = 12, Parent = row })
	end

	local status = itemStatus(item)
	if status == "Equipped" then
		if detailHover then
			detailButton:SetStyle("Red")
			detailButton:SetText("ÇIKAR")
		else
			detailButton:SetStyle("Blue")
			detailButton:SetText("✓ KUŞANILDI")
		end
	elseif status == "Owned" then
		detailButton:SetStyle("Blue")
		detailButton:SetText("KUŞAN")
	else
		detailButton:SetStyle(state.Coins >= item.Price and "Green" or "Gray")
		detailButton:SetText(item.Price == 0 and "AL · ÜCRETSİZ" or ("SATIN AL · " .. priceText(item)))
	end
end

local function refreshAll()
	for _, item in ipairs(ShopItems.Items) do
		updateCard(item)
	end
	updateDetail()
end

local function selectItem(itemId)
	state.Selected = itemId
	refreshAll()
end

-- Satın alma / kuşanma
local confirmItem = nil

local function closeConfirm()
	confirmItem = nil
	modal.Visible = false
	modalDim.Visible = false
end

local function openConfirm(item)
	if state.Coins < item.Price then
		showToast(("Yetersiz coin! %s coin daha lazım."):format(formatNumber(item.Price - state.Coins)), false)
		return
	end
	confirmItem = item
	for _, child in ipairs(modalIconHolder:GetChildren()) do
		child:Destroy()
	end
	iconView(item, UDim2.fromScale(1, 1), 70).Parent = modalIconHolder
	for _, child in ipairs(modalIconHolder:GetChildren()) do
		child.ZIndex = 31
	end
	modalName.Text = item.Name
	modalCost.Text = priceText(item)
	modalDim.Visible = true
	modal.Visible = true
	modalScale.Scale = baseScale * 0.85
	tween(modalScale, 0.2, { Scale = baseScale }, Enum.EasingStyle.Back)
end

local function applyResult(result)
	if result and result.message then
		showToast(result.message, result.ok)
	end
end

local function requestPurchase(item)
	if state.Busy then
		return
	end
	state.Busy = true
	local ok, result = pcall(function()
		return Remotes.Purchase:InvokeServer(item.Id)
	end)
	state.Busy = false
	applyResult(ok and result or { ok = false, message = "Bağlantı hatası, tekrar dene." })
end

local function requestEquip(item)
	if state.Busy then
		return
	end
	state.Busy = true
	local ok, result = pcall(function()
		return Remotes.Equip:InvokeServer(item.Id)
	end)
	state.Busy = false
	applyResult(ok and result or { ok = false, message = "Bağlantı hatası, tekrar dene." })
end

local function primaryAction(item)
	if itemStatus(item) == "Locked" then
		openConfirm(item)
	else
		requestEquip(item)
	end
end

-- Kartlar
local function createCard(item)
	local rarity = ShopItems.Rarities[item.Rarity]
	local root = create("TextButton", {
		Name = item.Id,
		Text = "",
		AutoButtonColor = false,
		BackgroundColor3 = THEME.Card,
		LayoutOrder = item.Order,
		ZIndex = 12,
		Parent = scroll,
	}, { corner(14) })
	local cardStroke = stroke(THEME.Accent, 3)
	cardStroke.Enabled = false
	cardStroke.Parent = root

	create("Frame", {
		Name = "Glow",
		Size = UDim2.new(1, 0, 0, 92),
		BackgroundColor3 = rarity.Color,
		BorderSizePixel = 0,
		ZIndex = 12,
		Parent = root,
	}, {
		corner(14),
		create("UIGradient", {
			Rotation = 90,
			Transparency = NumberSequence.new(0.6, 1),
		}),
	})

	if item.New then
		local badge = text({
			Name = "NewBadge",
			AnchorPoint = Vector2.new(1, 0),
			Position = UDim2.new(1, -8, 0, 8),
			Size = UDim2.fromOffset(42, 18),
			BackgroundTransparency = 0,
			BackgroundColor3 = STYLES.Red[1],
			Text = "YENİ",
			Font = FONT.Black,
			TextSize = 10,
			ZIndex = 14,
			Parent = root,
		})
		corner(6).Parent = badge
	end

	local icon = iconView(item, UDim2.new(1, 0, 0, 70), 54)
	icon.Position = UDim2.fromOffset(0, 10)
	icon.ZIndex = 13
	icon.Parent = root

	text({
		Position = UDim2.new(0, 6, 0, 86),
		Size = UDim2.new(1, -12, 0, 20),
		Text = item.Name,
		Font = FONT.Black,
		TextSize = 15,
		TextTruncate = Enum.TextTruncate.AtEnd,
		ZIndex = 13,
		Parent = root,
	})
	text({
		Position = UDim2.fromOffset(0, 106),
		Size = UDim2.new(1, 0, 0, 14),
		Text = rarity.Name:upper(),
		TextSize = 11,
		TextColor3 = rarity.Color,
		ZIndex = 13,
		Parent = root,
	})

	local price = button3D({
		Name = "Price",
		Position = UDim2.new(0, 10, 1, -47),
		Size = UDim2.new(1, -20, 0, 37),
		Radius = 10,
		Depth = 3,
		Parent = root,
	})
	price.Holder.ZIndex = 13
	price.Face.ZIndex = 14

	local scale = create("UIScale", { Parent = root })
	root.MouseEnter:Connect(function()
		tween(scale, 0.12, { Scale = 1.03 })
	end)
	root.MouseLeave:Connect(function()
		tween(scale, 0.12, { Scale = 1 })
	end)
	root.Activated:Connect(function()
		selectItem(item.Id)
	end)
	price.Activated:Connect(function()
		selectItem(item.Id)
		primaryAction(item)
	end)

	cards[item.Id] = { Root = root, Stroke = cardStroke, Price = price }
	updateCard(item)
end

local function rebuildGrid()
	for _, card in pairs(cards) do
		card.Root:Destroy()
	end
	table.clear(cards)

	local query = state.Search:lower()
	local first = nil
	for _, item in ipairs(ShopItems.Items) do
		local matches = item.Category == state.Category
			and (query == "" or item.Name:lower():find(query, 1, true) ~= nil)
		if matches then
			createCard(item)
			first = first or item.Id
		end
	end
	emptyLabel.Visible = first == nil
	scroll.CanvasPosition = Vector2.zero

	if not cards[state.Selected] then
		state.Selected = first
	end
	refreshAll()
end

-- Sekmeler
local function setCategory(categoryId)
	state.Category = categoryId
	for id, tab in pairs(tabs) do
		local active = id == categoryId
		tab.Holder.BackgroundColor3 = active and STYLES.Gold[3] or THEME.Tab
		tab.Face.BackgroundColor3 = active and THEME.Accent or THEME.Tab
		tab.Face.Size = UDim2.new(1, 0, 1, active and -4 or 0)
		tab.Label.TextColor3 = active and Color3.fromRGB(58, 38, 0) or THEME.Muted
	end
	rebuildGrid()
end

for i, category in ipairs(ShopItems.Categories) do
	local holder = create("Frame", {
		Name = category.Id,
		Size = UDim2.new(1, 0, 0, 48),
		BackgroundColor3 = THEME.Tab,
		LayoutOrder = i,
		ZIndex = 11,
		Parent = tabList,
	}, { corner(12) })
	local face = create("TextButton", {
		Text = "",
		AutoButtonColor = false,
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = THEME.Tab,
		ZIndex = 12,
		Parent = holder,
	}, { corner(12) })
	text({ Position = UDim2.fromOffset(12, 0), Size = UDim2.new(0, 24, 1, 0), Text = category.Icon, TextSize = 20, ZIndex = 13, Parent = face })
	local label = text({
		Position = UDim2.fromOffset(44, 0),
		Size = UDim2.new(1, -48, 1, 0),
		Text = category.Name,
		TextSize = 15,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextTruncate = Enum.TextTruncate.AtEnd,
		ZIndex = 13,
		Parent = face,
	})
	face.Activated:Connect(function()
		if state.Category ~= category.Id then
			setCategory(category.Id)
		end
	end)
	tabs[category.Id] = { Holder = holder, Face = face, Label = label }
end

-- Açma / kapama ve ölçekleme
local function updateScale()
	local viewport = workspace.CurrentCamera.ViewportSize
	baseScale = math.clamp(math.min(viewport.X * 0.92 / BASE_SIZE.X, viewport.Y * 0.86 / BASE_SIZE.Y), 0.45, 1.35)
	if state.Open then
		mainScale.Scale = baseScale
	end
	modalScale.Scale = baseScale
	hudScale.Scale = math.clamp(baseScale, 0.7, 1.1)
	toastScale.Scale = math.clamp(baseScale, 0.7, 1.1)
end

local function setOpen(open)
	if state.Open == open then
		return
	end
	state.Open = open
	if open then
		main.Visible = true
		backdrop.Visible = true
		mainScale.Scale = baseScale * 0.85
		tween(mainScale, 0.25, { Scale = baseScale }, Enum.EasingStyle.Back)
		tween(backdrop, 0.25, { BackgroundTransparency = 0.55 })
		refreshAll()
	else
		closeConfirm()
		searchBox:ReleaseFocus()
		tween(backdrop, 0.15, { BackgroundTransparency = 1 })
		tween(mainScale, 0.15, { Scale = baseScale * 0.85 }, Enum.EasingStyle.Quad, Enum.EasingDirection.In).Completed:Connect(function()
			if not state.Open then
				main.Visible = false
				backdrop.Visible = false
			end
		end)
	end
end

----------------------------------------------------------------------
-- Bağlantılar
----------------------------------------------------------------------

hudButton.Activated:Connect(function()
	setOpen(not state.Open)
end)
closeButton.Activated:Connect(function()
	setOpen(false)
end)
backdrop.Activated:Connect(function()
	setOpen(false)
end)
cancelButton.Activated:Connect(closeConfirm)
modalDim.Activated:Connect(closeConfirm)
confirmButton.Activated:Connect(function()
	local item = confirmItem
	closeConfirm()
	if item then
		requestPurchase(item)
	end
end)

detailButton.Activated:Connect(function()
	local item = ShopItems.ById[state.Selected]
	if item then
		primaryAction(item)
	end
end)
detailButton.Face.MouseEnter:Connect(function()
	detailHover = true
	updateDetail()
end)
detailButton.Face.MouseLeave:Connect(function()
	detailHover = false
	updateDetail()
end)

plusButton.Activated:Connect(function()
	if Settings.CoinProduct.Id ~= 0 then
		MarketplaceService:PromptProductPurchase(player, Settings.CoinProduct.Id)
	elseif Settings.PassiveIncome.Amount > 0 then
		showToast(("Oyunda kaldıkça her %d sn'de +%d coin kazanırsın!"):format(Settings.PassiveIncome.Interval, Settings.PassiveIncome.Amount), true)
	end
end)

searchBox:GetPropertyChangedSignal("Text"):Connect(function()
	state.Search = searchBox.Text
	rebuildGrid()
end)

UserInputService.InputBegan:Connect(function(input, gameProcessed)
	if not gameProcessed and input.KeyCode == Settings.ToggleKey then
		setOpen(not state.Open)
	end
end)

workspace.CurrentCamera:GetPropertyChangedSignal("ViewportSize"):Connect(updateScale)
updateScale()

Remotes.DataChanged.OnClientEvent:Connect(function(data)
	state.Owned = data.Owned or {}
	state.Equipped = data.Equipped or {}
	refreshAll()
end)

task.spawn(function()
	local coins = player:WaitForChild("leaderstats"):WaitForChild(Settings.CurrencyName)
	setCoins(coins.Value)
	coins.Changed:Connect(function(value)
		setCoins(value)
		updateDetail()
	end)
end)

setCategory(state.Category)

task.spawn(function()
	local data = Remotes.GetData:InvokeServer()
	if data then
		state.Owned = data.Owned or {}
		state.Equipped = data.Equipped or {}
		refreshAll()
	end
end)
