#!/usr/bin/env python
###############################################################################
#                                                                             #
#    extract.py                                                               #
#                                                                             #
#    Classes for data extraction                                              #
#                                                                             #
#    Copyright (C) Michael Imelfort, Tim Lamberton                            #
#                                                                             #
###############################################################################
#                                                                             #
#          .d8888b.                                    888b     d888          #
#         d88P  Y88b                                   8888b   d8888          #
#         888    888                                   88888b.d88888          #
#         888        888d888 .d88b.   .d88b.  88888b.  888Y88888P888          #
#         888  88888 888P"  d88""88b d88""88b 888 "88b 888 Y888P 888          #
#         888    888 888    888  888 888  888 888  888 888  Y8P  888          #
#         Y88b  d88P 888    Y88..88P Y88..88P 888 d88P 888   "   888          #
#          "Y8888P88 888     "Y88P"   "Y88P"  88888P"  888       888          #
#                                             888                             #
#                                             888                             #
#                                             888                             #
#                                                                             #
###############################################################################
#                                                                             #
#    This program is free software: you can redistribute it and/or modify     #
#    it under the terms of the GNU General Public License as published by     #
#    the Free Software Foundation, either version 3 of the License, or        #
#    (at your option) any later version.                                      #
#                                                                             #
#    This program is distributed in the hope that it will be useful,          #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of           #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            #
#    GNU General Public License for more details.                             #
#                                                                             #
#    You should have received a copy of the GNU General Public License        #
#    along with this program. If not, see <http://www.gnu.org/licenses/>.     #
#                                                                             #
###############################################################################

__author__ = "Michael Imelfort, Tim Lamberton"
__copyright__ = "Copyright 2012-2015"
__credits__ = ["Michael Imelfort", "Tim Lamberton"]
__license__ = "GPL3"
__version__ = "0.2.11"
__maintainer__ = "Tim Lamberton"
__email__ = "t.lamberton@uq.edu.au"
__status__ = "Development"

###############################################################################
import os
import sys
import errno
import numpy as np
import scipy.spatial.distance as sp_distance
from bamm.bamExtractor import BamExtractor as BMBE

# local imports
from profileManager import ProfileManager
from binManager import BinManager
from classification import ClassificationManager
from mstore import ContigParser
from utils import makeSurePathExists
import distance


###############################################################################
###############################################################################
###############################################################################
###############################################################################

class BinExtractor:
    """Used for extracting reads and contigs based on bin assignments"""
    def __init__(self, dbFileName,
                 folder='',
                 ):
        self.dbFileName = dbFileName
        self._pm = ProfileManager(self.dbFileName)
        self._outDir = os.getcwd() if folder == "" else folder
        # make the dir if need be
        makeSurePathExists(self._outDir)

    def loadProfile(self, timer, bids=[], cutoff=0):
        if bids is None or bids == []:
            return self._pm.loadData(timer, 
                                     loadBins=True,
                                     bids=[0],
                                     removeBins=True,
                                     minLength=cutoff
                                    )
        else:
            return self._pm.loadData(timer,
                                     loadBins=True,
                                     bids=bids,
                                     minLength=cutoff
                                    )

    def extractContigs(self,
                       timer,
                       bids=[],
                       fasta=[],
                       prefix='',
                       cutoff=0):
        """Extract contigs and write to file"""
        
        if prefix is None or prefix == '':
            prefix=os.path.basename(self.dbFileName) \
                            .replace(".gm", "") \
                            .replace(".sm", "")
                            
        profile = self.loadProfile(timer, bids, cutoff)
        bm = BinManager(profile)
        
        # load all the contigs which have been assigned to bins
        cp = ContigParser()
        # contigs looks like cid->seq
        contigs = {}
        import mimetypes
        try:
            for file_name in fasta:
                gm_open = open
                try:
                    # handle gzipped files
                    mime = mimetypes.guess_type(file_name)
                    if mime[1] == 'gzip':
                        import gzip
                        gm_open = gzip.open
                except:
                    print "Error when guessing contig file mimetype"
                    raise
                with gm_open(file_name, "r") as f:
                    contigs = cp.getWantedSeqs(f, profile.contigNames, storage=contigs)
        except:
            print "Could not parse contig file:",fasta[0],sys.exc_info()[0]
            raise

        # now print out the sequences
        print "Writing files"
        for bid in bm.getBids():
            file_name = os.path.join(self._outDir, "%s_bin_%d.fna" % (prefix, bid))
            try:
                with open(file_name, 'w') as f:
                    for cid in profile.contigNames[bm.getBinIndices(bid)]:
                        if(cid in contigs):
                            f.write(">%s\n%s\n" % (cid, contigs[cid]))
                        else:
                            print "These are not the contigs you're looking for. ( %s )" % (cid)
            except:
                print "Could not open file for writing:",file_name,sys.exc_info()[0]
                raise

    def extractReads(self,
                     timer,
                     bids=[],
                     bams=[],
                     prefix="",
                     mixBams=False,
                     mixGroups=False,
                     mixReads=False,
                     interleaved=False,
                     bigFile=False,
                     headersOnly=False,
                     minMapQual=0,
                     maxMisMatches=1000,
                     useSuppAlignments=False,
                     useSecondaryAlignments=False,
                     threads=1,
                     verbose=False):
        """Extract reads from bam files and write to file

        All logic is handled by BamM <- soon to be wrapped by StoreM"""
        # load data
        profile = self.loadProfile(timer, bids)
        bm = BinManager(profile) # bins

        print "Extracting reads"

        # work out a set of targets to pass to the parser
        targets = []
        group_names = []
        for bid in bm.getBids():
            group_names.append("BIN_%d" % bid)
            row_indices = bm.getBinIndices(bid)
            targets.append(list(profile.contigNames[row_indices]))

        # get something to parse the bams with
        bam_parser = BMBE(targets,
                          bams,
                          groupNames=group_names,
                          prefix=prefix,
                          outFolder=self._outDir,
                          mixBams=mixBams,
                          mixGroups=mixGroups,
                          mixReads=mixReads,
                          interleaved=interleaved,
                          bigFile=bigFile,
                          headersOnly=headersOnly,
                          minMapQual=minMapQual,
                          maxMisMatches=maxMisMatches,
                          useSuppAlignments=useSuppAlignments,
                          useSecondaryAlignments=useSecondaryAlignments)

        bam_parser.extract(threads=threads,
                           verbose=verbose)
                           
                           
class MarkerExtractor:
    def __init__(self,
                 dbFileName,
                 markerFileName=None,
                 folder=''
                 ):
        self.dbFileName = dbFileName
        self.markerFileName = markerFileName
        self._pm = ProfileManager(self.dbFileName, self.markerFileName)
        self._outDir = os.getcwd() if folder == "" else folder
        # make the dir if need be
        makeSurePathExists(self._outDir)

    def loadProfile(self, timer, bids=[], cutoff=0):
        bids = [] if bids is None else bids
        return self._pm.loadData(timer,
                                 loadBins=True,
                                 loadMarkers=True,
                                 bids=bids,
                                 minLength=cutoff
                                )
        
    def extractMappingInfo(self,
                           timer,
                           bids=[],
                           prefix='',
                           cutoff=0
                           ):
        """Extract markers from bins and write to file"""
        if prefix is None or prefix == '':
            prefix=os.path.basename(self.dbFileName) \
                            .replace(".gm", "") \
                            .replace(".sm", "")
        
        profile = self.loadProfile(timer, bids, cutoff)
        bm = BinManager(profile)
        dm = ClassificationManager(profile.markers).makeDistances()
        
        # load all the contigs which have been assigned to bins

        # now print out the sequences
        print "Writing files"
        for bid in bm.getBids():
            file_name = os.path.join(self._outDir, "%s_bin_%d.txt" % (prefix, bid))
            
            bin_indices = bm.getBinIndices([bid])
            idx = np.flatnonzero(np.in1d(profile.markers.rowIndices, bin_indices))
            
            labels = profile.markers.markerNames[idx]
            taxstrings = profile.markers.taxstrings[idx]
            cnames = profile.contigNames[profile.markers.rowIndices[idx]]
            dists = sp_distance.squareform(dm[distance.pcoords(idx, profile.markers.numMappings)])
            
            try:
                with open(file_name, 'w') as f:
                    #labels and lineages
                    f.write('#info table\n%s\n' % '\t'.join(['label', 'taxonomy', 'contig_name']))
                    for (label, tax, cname) in zip(labels, taxstrings, cnames):
                        f.write('%s\n' % '\t'.join([label, '\'%s\'' % tax, cname]))
                    
                    #distance table
                    f.write('\n#distance table\n')
                    for row in dists:
                        f.write('%s\n' % ' '.join(row.astype(int).astype(str)))
            except:
                print "Could not open file for writing:",file_name,sys.exc_info()[0]
                raise
    
###############################################################################
###############################################################################
###############################################################################
###############################################################################
