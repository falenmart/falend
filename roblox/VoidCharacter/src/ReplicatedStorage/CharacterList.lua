-- CharacterList (ModuleScript) -> ReplicatedStorage
-- Seçim menüsündeki karakterler. Yeni karakter eklemek için buraya bir satır ekle.

return {
	{
		Id = "Sentry",
		Name = "Sentry (Void)",
		Description = "Uçar, simsiyah Void formuna girer, gölgeleriyle düşmanlarını yok eder. Cutscene'li ultimate.",
		Keys = "F uç · Z Void · X Kavrayış · C Dalga · G Boşluk",
		Color = Color3.fromRGB(30, 32, 45),
		Accent = Color3.fromRGB(230, 235, 255),
	},
	{
		Id = "Kaneki",
		Name = "Ken Kaneki",
		Description = "Parmağını kütletip kagunesini açar. Dört dokunaçla saplar, savurur ve yakalar.",
		Keys = "E Kagune · X Saplama · C Fırtına · V Yakalama",
		Color = Color3.fromRGB(45, 8, 12),
		Accent = Color3.fromRGB(255, 70, 80),
	},
	{
		Id = "None",
		Name = "Normal",
		Description = "Güç yok, sıradan karakter.",
		Keys = "",
		Color = Color3.fromRGB(35, 35, 38),
		Accent = Color3.fromRGB(200, 200, 205),
	},
}
