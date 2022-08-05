<?php
header('Content-Type: text/plain');
$logid = uniqid();
function log_puts($msg) {
	error_log("PORTCHECK - " . $GLOBALS["logid"] . " - " . $msg);
}
function error_exit($err) {
	log_puts($err);
	echo "ERROR " . $err;
	exit(404);
}
$address = $_SERVER["REMOTE_ADDR"];
$scheme  = isset($_GET['scheme' ]) ? $_GET['scheme' ] : "http";
$port    = isset($_GET['port'   ]) ? $_GET['port'   ] : "80";
$path    = isset($_GET['path'   ]) ? $_GET['path'   ] : "/";
$host    = isset($_GET['host'   ]) ? $_GET['host'   ] : $address;
$timeout = isset($_GET['timeout']) ? $_GET['timeout'] : "5000";
$retries = isset($_GET['retries']) ? $_GET['retries'] : "0";
$certchk = isset($_GET['certchk']) ? $_GET['certchk'] : "true";
$timeout = intval($timeout);
$retries = intval($retries);
$url = $scheme . "://" . $host . ":" . $port . $path;
$status = -1;
$err = NULL;
$data = "";
for ($retry = 0; $retry <= $retries; $retry += 1) {
	$ch = curl_init($url);
	if (!$ch) {
		error_exit("cannot initialize cURL");
	}
	curl_setopt($ch, CURLOPT_RETURNTRANSFER   , TRUE);
	curl_setopt($ch, CURLOPT_CONNECTTIMEOUT_MS, $timeout);
	curl_setopt($ch, CURLOPT_TIMEOUT_MS       , $timeout);
	if ($certchk == "false") {
	   curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
	   log_puts("certificate checking disabled");
	}	
	log_puts("checking <" . $url . ">, attempt #" . (1 + $retry) . "...");
	$data = curl_exec($ch);
	if (FALSE === $data) {
		$err = "cURL execution failed: " . curl_error($ch);
		curl_close($ch);
		continue;
	}
	$status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
	curl_close($ch);
	break;
}
if (-1 == $status) {
	error_exit($err);
}
log_puts("status is " . $status);
echo "OK " . $status . "\n" . $data;
?>