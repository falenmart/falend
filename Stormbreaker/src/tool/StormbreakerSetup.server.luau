--[[
	Stormbreaker Tool kurulumu.
	Import 3D ile gelen iki MeshPart'ı (veya onları içeren Model'i) bu Tool'un içine sürükle;
	oyun başlayınca bu script:
	  - "Stormbreaker_Handle" parçasının adını "Handle" yapar (Tool bunu ele verir),
	  - "Stormbreaker_Head"i Handle'a kaynaklar (WeldConstraint),
	  - Anchored/CanCollide/Massless ayarlarını yapar,
	  - SurfaceAppearances klasöründeki "Head" ve "Handle" görünümlerini ilgili parçalara takar
	    (haritaları Studio'da Properties penceresinden doldur).
]]
local tool = script.Parent

local function findPart(names: { string }): BasePart?
	for _, n in ipairs(names) do
		local direct = tool:FindFirstChild(n)
		if direct and direct:IsA("BasePart") then
			return direct
		end
	end
	for _, d in ipairs(tool:GetDescendants()) do
		if d:IsA("BasePart") and table.find(names, d.Name) then
			return d
		end
	end
	return nil
end

local handle = findPart({ "Handle", "Stormbreaker_Handle" })
local head = findPart({ "Head", "Stormbreaker_Head" })
if handle == nil or head == nil then
	warn("[Stormbreaker] Tool içinde 'Stormbreaker_Handle' ve 'Stormbreaker_Head' MeshPart'ları bulunamadı.")
	return
end

-- Import 3D bir Model içinde getirir; parçaları Tool'un doğrudan altına al
local oldModel = handle.Parent ~= tool and handle.Parent or nil
handle.Name = "Handle"
head.Name = "Head"
handle.Parent = tool
head.Parent = tool
if oldModel and oldModel:IsA("Model") and #oldModel:GetChildren() == 0 then
	oldModel:Destroy()
end

for _, p in ipairs({ handle, head }) do
	p.Anchored = false
	p.CanCollide = false
	p.CanQuery = false
	p.Massless = p == head
	p.CanTouch = p == handle
end

for _, w in ipairs(head:GetChildren()) do
	if w:IsA("WeldConstraint") or w:IsA("Weld") then
		w:Destroy()
	end
end
local weld = Instance.new("WeldConstraint")
weld.Name = "HeadWeld"
weld.Part0 = handle
weld.Part1 = head
weld.Parent = head

local looks = tool:FindFirstChild("SurfaceAppearances")
if looks then
	for _, pair in ipairs({ { "Head", head }, { "Handle", handle } }) do
		local sa = looks:FindFirstChild(pair[1])
		local part = pair[2] :: BasePart
		if sa and part:FindFirstChildOfClass("SurfaceAppearance") == nil then
			sa.Parent = part
		end
	end
end
