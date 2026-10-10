// Cyberpunk Kino: server script.
// Loaded through two lines the launcher adds to Kino's own maps/zombie_theater.gsc (sheets/hooks.json):
// pre_main() runs just before maps\_zombiemode::main(), post_main() just after it.
// The tables in init_tables() are generated from sheets/*.json by tools/build.py.

#include maps\_utility;
#include common_scripts\utility;
#include maps\_zombiemode_utility;

init_tables()
{
	level.cpk_weapons = [];
	cpk_add_weapon( "unity", "cpk_unity_zm", "cpk_unity_upgraded_zm", "start", 0, 0, "pistol", &"CYBERKINO_BUY_UNITY" );
	cpk_add_weapon( "lexington", "cpk_lexington_zm", "cpk_lexington_upgraded_zm", "box", 0, 3, "pistol", &"CYBERKINO_BUY_LEXINGTON" );
	cpk_add_weapon( "overture", "cpk_overture_zm", "cpk_overture_upgraded_zm", "box", 0, 3, "pistol", &"CYBERKINO_BUY_OVERTURE" );
	cpk_add_weapon( "sor22", "cpk_sor22_zm", "cpk_sor22_upgraded_zm", "wall", 500, 0, "sniper", &"CYBERKINO_BUY_SOR22" );
	cpk_add_weapon( "copperhead", "cpk_copperhead_zm", "cpk_copperhead_upgraded_zm", "wall", 1200, 0, "assault", &"CYBERKINO_BUY_COPPERHEAD" );
	cpk_add_weapon( "saratoga", "cpk_saratoga_zm", "cpk_saratoga_upgraded_zm", "wall", 1200, 0, "smg", &"CYBERKINO_BUY_SARATOGA" );
	cpk_add_weapon( "pulsar", "cpk_pulsar_zm", "cpk_pulsar_upgraded_zm", "wall", 1000, 0, "smg", &"CYBERKINO_BUY_PULSAR" );
	cpk_add_weapon( "shingen", "cpk_shingen_zm", "cpk_shingen_upgraded_zm", "wall", 1000, 0, "smg", &"CYBERKINO_BUY_SHINGEN" );
	cpk_add_weapon( "dian", "cpk_dian_zm", "cpk_dian_upgraded_zm", "wall", 1000, 0, "smg", &"CYBERKINO_BUY_DIAN" );
	cpk_add_weapon( "carnage", "cpk_carnage_zm", "cpk_carnage_upgraded_zm", "wall", 1500, 0, "shotgun", &"CYBERKINO_BUY_CARNAGE" );
	cpk_add_weapon( "tactician", "cpk_tactician_zm", "cpk_tactician_upgraded_zm", "wall", 500, 0, "shotgun", &"CYBERKINO_BUY_TACTICIAN" );
	cpk_add_weapon( "ajax", "cpk_ajax_zm", "cpk_ajax_upgraded_zm", "box", 0, 3, "assault", &"CYBERKINO_BUY_AJAX" );
	cpk_add_weapon( "masamune", "cpk_masamune_zm", "cpk_masamune_upgraded_zm", "box", 0, 3, "assault", &"CYBERKINO_BUY_MASAMUNE" );
	cpk_add_weapon( "sidewinder", "cpk_sidewinder_zm", "cpk_sidewinder_upgraded_zm", "box", 0, 3, "assault", &"CYBERKINO_BUY_SIDEWINDER" );
	cpk_add_weapon( "kyubi", "cpk_kyubi_zm", "cpk_kyubi_upgraded_zm", "box", 0, 3, "assault", &"CYBERKINO_BUY_KYUBI" );
	cpk_add_weapon( "crusher", "cpk_crusher_zm", "cpk_crusher_upgraded_zm", "box", 0, 3, "pistol", &"CYBERKINO_BUY_CRUSHER" );
	cpk_add_weapon( "zhuo", "cpk_zhuo_zm", "cpk_zhuo_upgraded_zm", "box", 0, 3, "smg", &"CYBERKINO_BUY_ZHUO" );
	cpk_add_weapon( "grad", "cpk_grad_zm", "cpk_grad_upgraded_zm", "box", 0, 3, "sniper", &"CYBERKINO_BUY_GRAD" );
	cpk_add_weapon( "defender", "cpk_defender_zm", "cpk_defender_upgraded_zm", "box", 0, 3, "mg", &"CYBERKINO_BUY_DEFENDER" );
	cpk_add_weapon( "achilles", "cpk_achilles_zm", "cpk_achilles_upgraded_zm", "rare", 0, 1, "sniper", &"CYBERKINO_BUY_ACHILLES" );
	cpk_add_weapon( "malorian", "cpk_malorian_zm", "cpk_malorian_upgraded_zm", "rare", 0, 1, "raygun", &"CYBERKINO_BUY_MALORIAN" );

	level.cpk_wall = [];
	level.cpk_start_swap = [];
	level.cpk_start_swap["m1911_zm"] = "cpk_unity_zm";
	level.cpk_start_swap["m1911_upgraded_zm"] = "cpk_unity_upgraded_zm";
	level.cpk_wall["m14_zm"] = "cpk_sor22_zm";
	level.cpk_wall["m16_zm"] = "cpk_copperhead_zm";
	level.cpk_wall["ak74u_zm"] = "cpk_saratoga_zm";
	level.cpk_wall["mp5k_zm"] = "cpk_pulsar_zm";
	level.cpk_wall["mpl_zm"] = "cpk_shingen_zm";
	level.cpk_wall["mp40_zm"] = "cpk_dian_zm";
	level.cpk_wall["pm63_zm"] = "cpk_dian_zm";
	level.cpk_wall["ithaca_zm"] = "cpk_carnage_zm";
	level.cpk_wall["rottweil72_zm"] = "cpk_tactician_zm";

	level.cpk_box_keep = [];
	level.cpk_box_keep["zombie_cymbal_monkey"] = true;

	level.cpk_cyber = [];
	cpk_add_cyber( "sandevistan", "slowmo", &"CYBERKINO_CHIP_SANDEVISTAN", &"CYBERKINO_HUD_SANDEVISTAN" );
	cpk_add_cyber( "tendons", "double_jump", &"CYBERKINO_CHIP_TENDONS", &"CYBERKINO_HUD_TENDONS" );
	cpk_add_cyber( "subdermal", "armor", &"CYBERKINO_CHIP_SUBDERMAL", &"CYBERKINO_HUD_SUBDERMAL" );
	cpk_add_cyber( "mantis", "mantis", &"CYBERKINO_CHIP_MANTIS", &"CYBERKINO_HUD_MANTIS" );

	level.cpk_rules = [];
	level.cpk_rules["first_round"] = 1;
	level.cpk_rules["specials_per_round"] = 1;
	level.cpk_rules["chip_lifetime_s"] = 30;
	level.cpk_rules["pickup_radius"] = 48;
	level.cpk_rules["lose_on_down"] = 1;

	level.cpk_sandevistan_timescale = "0.35";
	level.cpk_sandevistan_timescale_num = 0.35;
	level.cpk_sandevistan_duration = 4.0;
	level.cpk_sandevistan_cooldown = 20.0;
	level.cpk_tendons_velocity = 330.0;
	level.cpk_tendons_min_air = 0.15;
	level.cpk_subdermal_bonus = 100;
	level.cpk_mantis_weapon = "cpk_mantis_zm";
}

cpk_add_weapon( id, weapon, upgraded, role, cost, weight, vox, hint )
{
	s = SpawnStruct();
	s.id = id;
	s.weapon = weapon;
	s.upgraded = upgraded;
	s.role = role;
	s.cost = cost;
	s.weight = weight;
	s.vox = vox;
	s.hint = hint;
	PrecacheString( hint );
	level.cpk_weapons[ level.cpk_weapons.size ] = s;
}

cpk_add_cyber( id, effect, chip_text, hud_text )
{
	s = SpawnStruct();
	s.id = id;
	s.effect = effect;
	s.chip_text = chip_text;
	s.hud_text = hud_text;
	PrecacheString( chip_text );
	PrecacheString( hud_text );
	level.cpk_cyber[ level.cpk_cyber.size ] = s;
}

cpk_weight_common()
{
	return 3;
}

cpk_weight_rare()
{
	return 1;
}

pre_main()
{
	init_tables();

	PrecacheModel( "cpk_chip" );
	PrecacheString( &"CYBERKINO_CHIP_HINT" );
	PrecacheString( &"CYBERKINO_ALL_INSTALLED" );
	PrecacheString( &"CYBERKINO_SANDEVISTAN_ON" );
	PrecacheString( &"CYBERKINO_READY" );

	for( i = 0; i < level.cpk_weapons.size; i++ )
	{
		w = level.cpk_weapons[i];
		if( w.weight == 1 )
		{
			include_weapon( w.weapon, true, false, ::cpk_weight_rare );
		}
		else if( w.weight > 1 )
		{
			include_weapon( w.weapon, true, false, ::cpk_weight_common );
		}
		else
		{
			include_weapon( w.weapon, false );
		}
		include_weapon( w.upgraded, false );
		maps\_zombiemode_weapons::add_zombie_weapon( w.weapon, w.upgraded, w.hint, w.cost, w.vox, "" );
	}
	include_weapon( level.cpk_mantis_weapon, false );

	// Wall-buys: point each stock wall weapon's trigger at its Cyberpunk gun before Black Ops reads them.
	spawns = GetEntArray( "weapon_upgrade", "targetname" );
	for( i = 0; i < spawns.size; i++ )
	{
		stock = spawns[i].zombie_weapon_upgrade;
		if( !IsDefined( stock ) || !IsDefined( level.cpk_wall[ stock ] ) )
		{
			continue;
		}
		spawns[i].zombie_weapon_upgrade = level.cpk_wall[ stock ];
		if( IsDefined( spawns[i].target ) )
		{
			model = GetEnt( spawns[i].target, "targetname" );
			if( IsDefined( model ) )
			{
				model SetModel( GetWeaponModel( level.cpk_wall[ stock ] ) );
			}
		}
	}
}

post_main()
{
	// Mystery Box: only Cyberpunk guns (plus the equipment in sheets/box_keep.json).
	keys = GetArrayKeys( level.zombie_weapons );
	for( i = 0; i < keys.size; i++ )
	{
		if( IsSubStr( keys[i], "cpk_" ) || IsDefined( level.cpk_box_keep[ keys[i] ] ) )
		{
			continue;
		}
		level.zombie_weapons[ keys[i] ].is_in_box = false;
	}

	level thread cpk_player_watch();
	level thread cpk_special_loop();
}

// ---------------------------------------------------------------- players

cpk_player_watch()
{
	for( ;; )
	{
		players = get_players();
		for( i = 0; i < players.size; i++ )
		{
			p = players[i];
			if( !IsDefined( p.cpk_init ) )
			{
				p.cpk_init = true;
				p thread cpk_player_init();
			}
			keys = GetArrayKeys( level.cpk_start_swap );
			for( k = 0; k < keys.size; k++ )
			{
				if( p HasWeapon( keys[k] ) )
				{
					p cpk_swap_weapon( keys[k], level.cpk_start_swap[ keys[k] ] );
				}
			}
		}
		wait( 0.5 );
	}
}

cpk_swap_weapon( stock, ours )
{
	current = self GetCurrentWeapon();
	self TakeWeapon( stock );
	self GiveWeapon( ours );
	self GiveMaxAmmo( ours );
	if( current == stock )
	{
		self SwitchToWeapon( ours );
	}
}

cpk_player_init()
{
	self endon( "disconnect" );
	self.cpk_have = [];
	for( i = 0; i < level.cpk_cyber.size; i++ )
	{
		self.cpk_have[ level.cpk_cyber[i].id ] = false;
	}
	self cpk_hud_create();
	self thread cpk_downed_watch();
	self thread cpk_sandevistan_loop();
	self thread cpk_tendons_loop();
	self thread cpk_armor_loop();
}

cpk_hud_create()
{
	self.cpk_hud = [];
	for( i = 0; i < level.cpk_cyber.size; i++ )
	{
		h = NewClientHudElem( self );
		h.alignX = "left";
		h.alignY = "top";
		h.horzAlign = "left";
		h.vertAlign = "top";
		h.x = 8;
		h.y = 90 + ( i * 16 );
		h.fontScale = 1.3;
		h.color = ( 0.35, 1, 0.9 );
		h.alpha = 0;
		h SetText( level.cpk_cyber[i].hud_text );
		self.cpk_hud[ level.cpk_cyber[i].id ] = h;
	}
}

cpk_downed_watch()
{
	self endon( "disconnect" );
	for( ;; )
	{
		self waittill( "player_downed" );
		if( level.cpk_rules["lose_on_down"] != 1 )
		{
			continue;
		}
		for( i = 0; i < level.cpk_cyber.size; i++ )
		{
			id = level.cpk_cyber[i].id;
			if( self.cpk_have[ id ] && level.cpk_cyber[i].effect == "mantis" )
			{
				self cpk_take_mantis();
			}
			self.cpk_have[ id ] = false;
			self.cpk_hud[ id ].alpha = 0;
		}
	}
}

cpk_next_chip()
{
	pool = [];
	for( i = 0; i < level.cpk_cyber.size; i++ )
	{
		if( !self.cpk_have[ level.cpk_cyber[i].id ] )
		{
			pool[ pool.size ] = level.cpk_cyber[i];
		}
	}
	if( pool.size == 0 )
	{
		return undefined;
	}
	return pool[ RandomInt( pool.size ) ];
}

cpk_install( cyber )
{
	self.cpk_have[ cyber.id ] = true;
	self.cpk_hud[ cyber.id ].alpha = 1;
	self iPrintLnBold( cyber.chip_text );
	if( cyber.effect == "mantis" )
	{
		self cpk_give_mantis();
	}
}

// ---------------------------------------------------------------- cyberware

cpk_sandevistan_loop()
{
	self endon( "disconnect" );
	ready_at = 0;
	for( ;; )
	{
		wait( 0.05 );
		if( !self.cpk_have["sandevistan"] || GetTime() < ready_at )
		{
			continue;
		}
		if( self AdsButtonPressed() && self MeleeButtonPressed() )
		{
			ready_at = GetTime() + int( ( level.cpk_sandevistan_duration + level.cpk_sandevistan_cooldown ) * 1000 );
			self thread cpk_sandevistan_run();
		}
	}
}

cpk_sandevistan_run()
{
	self endon( "disconnect" );
	self iPrintLnBold( &"CYBERKINO_SANDEVISTAN_ON" );
	SetDvar( "timescale", level.cpk_sandevistan_timescale );
	// Game time runs slower while it is on, so wait the scaled time to last duration real seconds.
	wait( level.cpk_sandevistan_duration * level.cpk_sandevistan_timescale_num );
	SetDvar( "timescale", "1" );
	wait( level.cpk_sandevistan_cooldown );
	if( self.cpk_have["sandevistan"] )
	{
		self iPrintLn( &"CYBERKINO_READY" );
	}
}

cpk_tendons_loop()
{
	self endon( "disconnect" );
	air = 0;
	used = false;
	released = false;
	for( ;; )
	{
		wait( 0.05 );
		if( !self.cpk_have["tendons"] || self IsOnGround() )
		{
			air = 0;
			used = false;
			released = false;
			continue;
		}
		air = air + 0.05;
		if( !self JumpButtonPressed() )
		{
			released = true;
			continue;
		}
		if( released && !used && air >= level.cpk_tendons_min_air )
		{
			used = true;
			vel = self GetVelocity();
			self SetVelocity( ( vel[0], vel[1], level.cpk_tendons_velocity ) );
		}
	}
}

cpk_armor_loop()
{
	self endon( "disconnect" );
	applied = 0;
	for( ;; )
	{
		wait( 0.25 );
		if( !self.cpk_have["subdermal"] )
		{
			if( applied > 0 && self.maxhealth == applied )
			{
				self.maxhealth = applied - level.cpk_subdermal_bonus;
				if( self.health > self.maxhealth )
				{
					self.health = self.maxhealth;
				}
			}
			applied = 0;
			continue;
		}
		// Re-apply whenever something else (Juggernog, going down) set a new max health.
		if( self.maxhealth != applied )
		{
			self.maxhealth = self.maxhealth + level.cpk_subdermal_bonus;
			applied = self.maxhealth;
		}
	}
}

cpk_give_mantis()
{
	self.cpk_had_bowie = self HasWeapon( "bowie_knife_zm" );
	if( self HasWeapon( "knife_zm" ) )
	{
		self TakeWeapon( "knife_zm" );
	}
	if( self.cpk_had_bowie )
	{
		self TakeWeapon( "bowie_knife_zm" );
	}
	self GiveWeapon( level.cpk_mantis_weapon );
}

cpk_take_mantis()
{
	self TakeWeapon( level.cpk_mantis_weapon );
	if( is_true( self.cpk_had_bowie ) )
	{
		self GiveWeapon( "bowie_knife_zm" );
	}
	else
	{
		self GiveWeapon( "knife_zm" );
	}
}

// ---------------------------------------------------------------- special zombies and chips

cpk_special_loop()
{
	last = -1;
	for( ;; )
	{
		wait( 1 );
		if( !IsDefined( level.round_number ) || level.round_number == last )
		{
			continue;
		}
		last = level.round_number;
		if( last >= level.cpk_rules["first_round"] )
		{
			level thread cpk_mark_specials( last );
		}
	}
}

cpk_mark_specials( round )
{
	marked = 0;
	tries = 0;
	while( marked < level.cpk_rules["specials_per_round"] && tries < 180 && level.round_number == round )
	{
		wait( 1 );
		tries++;
		zombies = GetAiSpeciesArray( "axis", "all" );
		for( i = 0; i < zombies.size; i++ )
		{
			if( marked >= level.cpk_rules["specials_per_round"] )
			{
				break;
			}
			z = zombies[i];
			if( !IsAlive( z ) || IsDefined( z.cpk_special ) )
			{
				continue;
			}
			if( IsDefined( z.animname ) && z.animname != "zombie" )
			{
				continue;
			}
			z.cpk_special = true;
			z thread cpk_special_think();
			marked++;
		}
	}
}

cpk_special_think()
{
	if( IsDefined( level._effect["powerup_on"] ) )
	{
		PlayFxOnTag( level._effect["powerup_on"], self, "j_head" );
	}
	origin = self.origin;
	while( IsAlive( self ) )
	{
		origin = self.origin;
		wait( 0.1 );
	}
	level thread cpk_drop_chip( origin + ( 0, 0, 36 ) );
}

cpk_drop_chip( origin )
{
	chip = Spawn( "script_model", origin );
	chip SetModel( "cpk_chip" );
	if( IsDefined( level._effect["powerup_on"] ) )
	{
		PlayFxOnTag( level._effect["powerup_on"], chip, "tag_origin" );
	}
	trig = Spawn( "trigger_radius_use", origin, 0, level.cpk_rules["pickup_radius"], 72 );
	trig SetCursorHint( "HINT_NOICON" );
	trig SetHintString( &"CYBERKINO_CHIP_HINT" );
	chip.cpk_trig = trig;
	chip thread cpk_chip_spin();
	chip thread cpk_chip_wait();
	chip thread cpk_chip_timeout();
}

cpk_chip_spin()
{
	self endon( "death" );
	for( ;; )
	{
		self RotateYaw( 360, 2 );
		wait( 2 );
	}
}

cpk_chip_wait()
{
	self endon( "death" );
	for( ;; )
	{
		self.cpk_trig waittill( "trigger", player );
		if( !IsPlayer( player ) || player maps\_laststand::player_is_in_laststand() || !IsDefined( player.cpk_have ) )
		{
			continue;
		}
		cyber = player cpk_next_chip();
		if( !IsDefined( cyber ) )
		{
			player iPrintLnBold( &"CYBERKINO_ALL_INSTALLED" );
			continue;
		}
		player cpk_install( cyber );
		self.cpk_trig Delete();
		self Delete();
		return;
	}
}

cpk_chip_timeout()
{
	self endon( "death" );
	wait( level.cpk_rules["chip_lifetime_s"] );
	self.cpk_trig Delete();
	self Delete();
}
