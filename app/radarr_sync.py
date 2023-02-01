# Name: Pixlovarr Prune
# Coder: Marco Janssen (twitter @marc0janssen)
# date: 2022-12-24 23:22:02
# update: 2022-12-24 23:22:10

import logging
import sys
import configparser
import shutil

from datetime import datetime
from arrapi import RadarrAPI, exceptions


class radarrSync():

    def __init__(self):
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO)

        config_dir = "/config/"
        app_dir = "/app/"
        log_dir = "/logging/"

        self.config_file = "radarr_sync.ini"
        self.exampleconfigfile = "radarr_sync.ini.example"
        self.log_file = "radarr_sync.log"

        self.config_filePath = f"{config_dir}{self.config_file}"
        self.log_filePath = f"{log_dir}{self.log_file}"

        try:
            with open(self.config_filePath, "r") as f:
                f.close()
            try:
                self.config = configparser.ConfigParser()
                self.config.read(self.config_filePath)

                # RADARR_SOURCE
                self.radarrsource_url = self.config['RADARR_SOURCE']['URL']
                self.radarrsource_token = self.config['RADARR_SOURCE']['TOKEN']

                # RADARR_DESTINATION
                self.radarrdest_url = self.config['RADARR_DEST']['URL']
                self.radarrdest_token = self.config['RADARR_DEST']['TOKEN']

                # SYNC
                self.dry_run = True if (
                    self.config['SYNC']['DRY_RUN'] == "ON") else False
                self.enabled_run = True if (
                    self.config['SYNC']['ENABLED'] == "ON") else False
                self.verbose_logging = True if (
                    self.config['SYNC']['VERBOSE_LOGGING'] == "ON") else False

            except KeyError as e:
                logging.error(
                    f"Seems a key(s) {e} is missing from INI file. "
                    f"Please check for mistakes. Exiting."
                )

                sys.exit()

            except ValueError as e:
                logging.error(
                    f"Seems a invalid value in INI file. "
                    f"Please check for mistakes. Exiting. "
                    f"MSG: {e}"
                )

                sys.exit()

        except IOError or FileNotFoundError:
            logging.error(
                f"Can't open file {self.config_filePath}"
                f", creating example INI file."
            )

            shutil.copyfile(f'{app_dir}{self.exampleconfigfile}',
                            f'{config_dir}{self.exampleconfigfile}')
            sys.exit()

    def writeLog(self, init, msg):
        try:
            if init:
                logfile = open(self.log_filePath, "w")
            else:
                logfile = open(self.log_filePath, "a")
            logfile.write(f"{datetime.now()} - {msg}")
            logfile.close()
        except IOError:
            logging.error(
                f"Can't write file {self.log_filePath}."
            )

    def run(self):

        txtMsg = "Sync - Radarr Sync started"
        self.writeLog(True, f"{txtMsg}\n")
        if self.verbose_logging:
            logging.info(txtMsg)

        if not self.enabled_run:
            txtMsg = "Sync - Radarr sync disabled"
            logging.info(txtMsg)
            self.writeLog(False, f"{txtMsg}\n")
            sys.exit()

        # Connect to Radarr Source
        try:
            self.radarrsourceNode = RadarrAPI(
                self.radarrsource_url, self.radarrsource_token)
        except exceptions.ArrException as e:
            logging.error(
                f"Can't connect to Radarr source {e}"
            )

            sys.exit()

        # Connect to Radarr Destination
        try:
            self.radarrdestNode = RadarrAPI(
                self.radarrdest_url, self.radarrdest_token)
        except exceptions.ArrException as e:
            logging.error(
                f"Can't connect to Radarr destination {e}"
            )

            sys.exit()

        if self.dry_run:
            logging.info(
                "****************************************************")
            logging.info(
                "**** DRY RUN, NOTHING WILL BE DELETED OR SYNCED ****")
            logging.info(
                "****************************************************")

        self.sourceMedia = self.radarrsourceNode.all_movies()
        self.destMedia = self.radarrdestNode.all_movies()

        boolSynced = False
        boolFound = False

        for source in self.sourceMedia:
            for destination in self.destMedia:
                if (source.imdbId == destination.imdbId and source.imdbId) \
                        or (source.tmdbId == destination.tmdbId
                            and source.tmdbId):
                    boolFound = True
                    break

            if not boolFound:
                if source.imdbId:
                    dest = self.radarrdestNode.get_movie(imdb_id=source.imdbId)
                elif source.tmdbId:
                    dest = self.radarrdestNode.get_movie(tmdb_id=source.tmdbId)
                else:
                    # if both imdbID and tmdbID are NULL, continue to the next
                    continue

                if not dest.id:
                    boolSynced = True
                    txtMsg = (
                        f"Syncing the movie: {source.title}({source.year})")
                    self.writeLog(False, f"{txtMsg}\n")
                    logging.info(txtMsg)

                    try:
                        if not self.dry_run:
                            dest.add(
                                8,
                                1,
                                True,
                                True,
                                "released",
                                source.tags
                            )

                    except exceptions.Exists:
                        logging.warning(
                                    f"Movie {source.title}({source.year})"
                                    f" already exists on destination.")
            else:
                boolFound = False

        self.sourceMedia = self.radarrsourceNode.all_movies()
        self.destMedia = self.radarrdestNode.all_movies()

        boolFound = False

        for destination in self.destMedia:
            for source in self.sourceMedia:
                if (source.imdbId == destination.imdbId and
                    destination.imdbId) or \
                        (source.tmdbId == destination.tmdbId
                            and destination.tmdbId):
                    boolFound = True
                    break

            if not boolFound:
                if destination.imdbId:
                    source = self.radarrsourceNode.get_movie(
                        imdb_id=destination.imdbId)
                elif destination.tmdbId:
                    source = self.radarrsourceNode.get_movie(
                        tmdb_id=destination.tmdbId)
                else:
                    # if both imdbID and tmdbID are NULL, continue to the next
                    continue

                if not source.id:
                    boolSynced = True
                    txtMsg = (
                        f"Deleting the movie: {source.title}({source.year})")
                    self.writeLog(False, f"{txtMsg}\n")
                    logging.info(txtMsg)

                    try:
                        if not self.dry_run:
                            self.radarrdestNode.delete_movie(
                                movie_id=destination.id,
                                tmdb_id=None,
                                imdb_id=None,
                                addImportExclusion=False,
                                deleteFiles=True
                            )

                    except exceptions.NotFound:
                        logging.warning(
                                    f"Movie {dest.title}({dest.year})"
                                    f" doesn't exists on destination.")
            else:
                boolFound = False

        if not boolSynced:
            txtMsg = "Sync - No movies were synced."
            self.writeLog(False, f"{txtMsg}\n")
            if self.verbose_logging:
                logging.info(txtMsg)
        else:
            txtMsg = "Sync - Radarr Sync Ended"
            self.writeLog(False, f"{txtMsg}\n")
            if self.verbose_logging:
                logging.info(txtMsg)


if __name__ == '__main__':

    radarrsync = radarrSync()
    radarrsync.run()
    radarrsync = None
