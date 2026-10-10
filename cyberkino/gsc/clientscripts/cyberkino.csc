// Cyberpunk Kino: client script.
// Called from Kino's own clientscripts/zombie_theater.csc include_weapons() (sheets/hooks.json, client_include),
// so the Mystery Box shows the Cyberpunk guns while it spins. Generated from sheets/weapons.json by tools/build.py.

#include clientscripts\_utility;
#include clientscripts\_zombiemode_weapons;

include_weapons()
{
	include_weapon( "cpk_unity_zm", false );
	include_weapon( "cpk_unity_upgraded_zm", false );
	include_weapon( "cpk_lexington_zm", true );
	include_weapon( "cpk_lexington_upgraded_zm", false );
	include_weapon( "cpk_overture_zm", true );
	include_weapon( "cpk_overture_upgraded_zm", false );
	include_weapon( "cpk_sor22_zm", false );
	include_weapon( "cpk_sor22_upgraded_zm", false );
	include_weapon( "cpk_copperhead_zm", false );
	include_weapon( "cpk_copperhead_upgraded_zm", false );
	include_weapon( "cpk_saratoga_zm", false );
	include_weapon( "cpk_saratoga_upgraded_zm", false );
	include_weapon( "cpk_pulsar_zm", false );
	include_weapon( "cpk_pulsar_upgraded_zm", false );
	include_weapon( "cpk_shingen_zm", false );
	include_weapon( "cpk_shingen_upgraded_zm", false );
	include_weapon( "cpk_dian_zm", false );
	include_weapon( "cpk_dian_upgraded_zm", false );
	include_weapon( "cpk_carnage_zm", false );
	include_weapon( "cpk_carnage_upgraded_zm", false );
	include_weapon( "cpk_tactician_zm", false );
	include_weapon( "cpk_tactician_upgraded_zm", false );
	include_weapon( "cpk_ajax_zm", true );
	include_weapon( "cpk_ajax_upgraded_zm", false );
	include_weapon( "cpk_masamune_zm", true );
	include_weapon( "cpk_masamune_upgraded_zm", false );
	include_weapon( "cpk_sidewinder_zm", true );
	include_weapon( "cpk_sidewinder_upgraded_zm", false );
	include_weapon( "cpk_kyubi_zm", true );
	include_weapon( "cpk_kyubi_upgraded_zm", false );
	include_weapon( "cpk_crusher_zm", true );
	include_weapon( "cpk_crusher_upgraded_zm", false );
	include_weapon( "cpk_zhuo_zm", true );
	include_weapon( "cpk_zhuo_upgraded_zm", false );
	include_weapon( "cpk_grad_zm", true );
	include_weapon( "cpk_grad_upgraded_zm", false );
	include_weapon( "cpk_defender_zm", true );
	include_weapon( "cpk_defender_upgraded_zm", false );
	include_weapon( "cpk_achilles_zm", true );
	include_weapon( "cpk_achilles_upgraded_zm", false );
	include_weapon( "cpk_malorian_zm", true );
	include_weapon( "cpk_malorian_upgraded_zm", false );
	include_weapon( "cpk_mantis_zm", false );
}
